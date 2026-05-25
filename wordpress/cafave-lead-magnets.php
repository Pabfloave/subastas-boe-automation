<?php
/**
 * Plugin Name: CAFAVE Lead Magnets
 * Description: Captura de leads (checklist PDF gated + newsletter semanal con doble opt-in). Endpoints REST, shortcodes y emails transaccionales.
 * Version: 1.0.0
 * Author: CAFAVE INVESTMENT
 * Requires PHP: 7.4
 */

if (!defined('ABSPATH')) {
    exit;
}

// ════════════════════════════════════════════════════════════════
//  CONSTANTES Y CONFIGURACIÓN
// ════════════════════════════════════════════════════════════════

define('CAFAVE_LM_VERSION', '1.0.0');
define('CAFAVE_LM_DB_VERSION', '1');
define('CAFAVE_LM_NAMESPACE', 'cafave/v1');
define('CAFAVE_LM_PLUGIN_FILE', __FILE__);

// TTL de tokens
define('CAFAVE_LM_DOWNLOAD_TOKEN_TTL', DAY_IN_SECONDS);          // 24 h
define('CAFAVE_LM_CONFIRM_TOKEN_TTL', 7 * DAY_IN_SECONDS);       // 7 d

// PDF gated — ruta relativa a wp-content/uploads/
define('CAFAVE_LM_PDF_REL', 'cafave-lead-magnets/checklist-47-puntos.pdf');

// Rate limiting (anti-spam): nº submits por IP en ventana de tiempo
define('CAFAVE_LM_RATE_LIMIT_MAX', 5);
define('CAFAVE_LM_RATE_LIMIT_WINDOW', HOUR_IN_SECONDS);

// API key para acceso de Python al listado de subscribers
// (se debe definir en wp-config.php: define('CAFAVE_LM_API_KEY', '...');)
if (!defined('CAFAVE_LM_API_KEY')) {
    define('CAFAVE_LM_API_KEY', '');
}

// ════════════════════════════════════════════════════════════════
//  ACTIVACIÓN / DESACTIVACIÓN
// ════════════════════════════════════════════════════════════════

register_activation_hook(__FILE__, 'cafave_lm_activate');
function cafave_lm_activate() {
    global $wpdb;
    $charset_collate = $wpdb->get_charset_collate();
    $leads = $wpdb->prefix . 'cafave_leads';
    $subs  = $wpdb->prefix . 'cafave_subscribers';

    $sql_leads = "CREATE TABLE $leads (
        id bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
        nombre varchar(255) NOT NULL,
        email varchar(190) NOT NULL,
        source varchar(50) NOT NULL DEFAULT 'lead-magnet-checklist',
        tag varchar(50) NOT NULL DEFAULT 'lead-magnet-cold',
        interesado_informes tinyint(1) NOT NULL DEFAULT 0,
        consentimiento_rgpd tinyint(1) NOT NULL DEFAULT 0,
        ip_origen varchar(45) DEFAULT NULL,
        user_agent varchar(500) DEFAULT NULL,
        download_token varchar(64) DEFAULT NULL,
        token_expires_at datetime DEFAULT NULL,
        downloaded_at datetime DEFAULT NULL,
        download_count int(11) NOT NULL DEFAULT 0,
        fecha_alta datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY email_source (email, source),
        KEY tag (tag),
        KEY download_token (download_token)
    ) $charset_collate;";

    $sql_subs = "CREATE TABLE $subs (
        id bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
        email varchar(190) NOT NULL,
        provincia_pref varchar(2) DEFAULT NULL,
        status varchar(20) NOT NULL DEFAULT 'pending',
        confirm_token varchar(64) DEFAULT NULL,
        confirm_expires_at datetime DEFAULT NULL,
        unsubscribe_token varchar(64) NOT NULL,
        consentimiento_rgpd tinyint(1) NOT NULL DEFAULT 0,
        ip_origen varchar(45) DEFAULT NULL,
        fecha_alta datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        fecha_confirm datetime DEFAULT NULL,
        fecha_baja datetime DEFAULT NULL,
        last_sent_at datetime DEFAULT NULL,
        PRIMARY KEY (id),
        UNIQUE KEY email (email),
        KEY status (status),
        KEY confirm_token (confirm_token),
        KEY unsubscribe_token (unsubscribe_token)
    ) $charset_collate;";

    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    dbDelta($sql_leads);
    dbDelta($sql_subs);

    update_option('cafave_lm_db_version', CAFAVE_LM_DB_VERSION);

    // Asegurar el directorio del PDF gated
    $uploads = wp_upload_dir();
    $pdf_dir = trailingslashit($uploads['basedir']) . 'cafave-lead-magnets';
    if (!file_exists($pdf_dir)) {
        wp_mkdir_p($pdf_dir);
    }
    // Bloquear listado del directorio
    $htaccess = $pdf_dir . '/.htaccess';
    if (!file_exists($htaccess)) {
        file_put_contents($htaccess, "Options -Indexes\nDeny from all\n");
    }
}

// ════════════════════════════════════════════════════════════════
//  HELPERS
// ════════════════════════════════════════════════════════════════

function cafave_lm_generate_token(): string {
    return bin2hex(random_bytes(24)); // 48 hex chars
}

function cafave_lm_client_ip(): string {
    $ip = $_SERVER['HTTP_CF_CONNECTING_IP']
        ?? $_SERVER['HTTP_X_FORWARDED_FOR']
        ?? $_SERVER['REMOTE_ADDR']
        ?? '';
    if (strpos($ip, ',') !== false) {
        $ip = trim(explode(',', $ip)[0]);
    }
    return substr($ip, 0, 45);
}

function cafave_lm_rate_limited(string $ip): bool {
    $key = 'cafave_lm_rl_' . md5($ip);
    $count = (int) get_transient($key);
    if ($count >= CAFAVE_LM_RATE_LIMIT_MAX) {
        return true;
    }
    set_transient($key, $count + 1, CAFAVE_LM_RATE_LIMIT_WINDOW);
    return false;
}

function cafave_lm_api_key_check(WP_REST_Request $req): bool {
    $key = CAFAVE_LM_API_KEY;
    if (empty($key)) return false;
    $header = $req->get_header('X-API-Key');
    return hash_equals($key, (string) $header);
}

function cafave_lm_validate_email(string $email): bool {
    return is_email($email) && strlen($email) <= 190;
}

function cafave_lm_pdf_path(): string {
    $uploads = wp_upload_dir();
    return trailingslashit($uploads['basedir']) . CAFAVE_LM_PDF_REL;
}

function cafave_lm_brand_email_wrap(string $title, string $html_body): string {
    $site_name = get_bloginfo('name');
    $site_url  = home_url();
    return '<!DOCTYPE html><html lang="es"><body style="margin:0;background:#f3f4f6;font-family:Helvetica,Arial,sans-serif;color:#1f2937;">'
        . '<div style="max-width:560px;margin:0 auto;background:#fff;border-radius:6px;overflow:hidden;">'
        . '<div style="background:#0f1e3a;padding:24px;color:#fff;">'
        .   '<div style="font-size:11px;letter-spacing:3px;color:#93c5fd;text-transform:uppercase;">CAFAVE INVESTMENT</div>'
        .   '<div style="font-size:20px;font-weight:700;margin-top:6px;">' . esc_html($title) . '</div>'
        . '</div>'
        . '<div style="padding:28px 24px;font-size:15px;line-height:1.6;">' . $html_body . '</div>'
        . '<div style="background:#f3f4f6;padding:16px 24px;font-size:11px;color:#6b7280;text-align:center;">'
        .   esc_html($site_name) . ' · <a href="' . esc_url($site_url) . '" style="color:#2563eb;">' . esc_html($site_url) . '</a><br>'
        .   '<a href="' . esc_url($site_url . '/aviso-legal') . '" style="color:#6b7280;">Aviso legal y política de privacidad</a>'
        . '</div></div></body></html>';
}

// ════════════════════════════════════════════════════════════════
//  ENDPOINTS REST
// ════════════════════════════════════════════════════════════════

add_action('rest_api_init', function () {
    register_rest_route(CAFAVE_LM_NAMESPACE, '/leads/checklist', [
        'methods'             => 'POST',
        'callback'            => 'cafave_lm_handle_checklist_lead',
        'permission_callback' => '__return_true',
    ]);
    register_rest_route(CAFAVE_LM_NAMESPACE, '/checklist/download', [
        'methods'             => 'GET',
        'callback'            => 'cafave_lm_handle_checklist_download',
        'permission_callback' => '__return_true',
    ]);
    register_rest_route(CAFAVE_LM_NAMESPACE, '/newsletter/subscribe', [
        'methods'             => 'POST',
        'callback'            => 'cafave_lm_handle_newsletter_subscribe',
        'permission_callback' => '__return_true',
    ]);
    register_rest_route(CAFAVE_LM_NAMESPACE, '/newsletter/confirm', [
        'methods'             => 'GET',
        'callback'            => 'cafave_lm_handle_newsletter_confirm',
        'permission_callback' => '__return_true',
    ]);
    register_rest_route(CAFAVE_LM_NAMESPACE, '/newsletter/unsubscribe', [
        'methods'             => 'GET',
        'callback'            => 'cafave_lm_handle_newsletter_unsubscribe',
        'permission_callback' => '__return_true',
    ]);
    register_rest_route(CAFAVE_LM_NAMESPACE, '/newsletter/subscribers', [
        'methods'             => 'GET',
        'callback'            => 'cafave_lm_handle_list_subscribers',
        'permission_callback' => 'cafave_lm_api_key_check',
    ]);
});

// ──────────────────────────────
//  LEAD: descarga del checklist
// ──────────────────────────────

function cafave_lm_handle_checklist_lead(WP_REST_Request $req) {
    $ip = cafave_lm_client_ip();
    if (cafave_lm_rate_limited($ip)) {
        return new WP_Error('rate_limited', 'Demasiadas peticiones', ['status' => 429]);
    }

    // Honeypot — bots rellenan el campo "website"
    if (!empty(trim((string) $req->get_param('website')))) {
        return new WP_REST_Response(['ok' => true], 200); // mentimos al bot
    }

    $nombre              = sanitize_text_field((string) $req->get_param('nombre'));
    $email               = sanitize_email((string) $req->get_param('email'));
    $interesado_informes = $req->get_param('interesado_informes') ? 1 : 0;
    $consent             = $req->get_param('consent') ? 1 : 0;

    if (empty($nombre) || mb_strlen($nombre) > 100) {
        return new WP_Error('invalid_name', 'Nombre inválido', ['status' => 400]);
    }
    if (!cafave_lm_validate_email($email)) {
        return new WP_Error('invalid_email', 'Email inválido', ['status' => 400]);
    }
    if (!$consent) {
        return new WP_Error('no_consent', 'Debes aceptar la política de privacidad', ['status' => 400]);
    }

    global $wpdb;
    $table = $wpdb->prefix . 'cafave_leads';
    $token = cafave_lm_generate_token();
    $expires = gmdate('Y-m-d H:i:s', time() + CAFAVE_LM_DOWNLOAD_TOKEN_TTL);
    $ua = substr((string) ($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 500);

    // Upsert por email+source (UNIQUE KEY)
    $wpdb->query($wpdb->prepare(
        "INSERT INTO $table (nombre, email, source, tag, interesado_informes, consentimiento_rgpd, ip_origen, user_agent, download_token, token_expires_at)
         VALUES (%s, %s, 'lead-magnet-checklist', 'lead-magnet-cold', %d, 1, %s, %s, %s, %s)
         ON DUPLICATE KEY UPDATE
           nombre = VALUES(nombre),
           interesado_informes = VALUES(interesado_informes),
           ip_origen = VALUES(ip_origen),
           user_agent = VALUES(user_agent),
           download_token = VALUES(download_token),
           token_expires_at = VALUES(token_expires_at)",
        $nombre, $email, $interesado_informes, $ip, $ua, $token, $expires
    ));

    // Enviar email con link de descarga
    $download_url = rest_url(CAFAVE_LM_NAMESPACE . '/checklist/download') . '?token=' . urlencode($token);
    $expires_human = wp_date('j \d\e F \d\e Y \a \l\a\s G:i', strtotime($expires));

    $body = '<p>Hola ' . esc_html($nombre) . ',</p>'
        . '<p>Gracias por solicitar el <strong>Checklist 47 puntos antes de pujar</strong>. Aquí tienes tu enlace de descarga:</p>'
        . '<p style="text-align:center;margin:24px 0;">'
        .   '<a href="' . esc_url($download_url) . '" style="background:#2563eb;color:#fff;text-decoration:none;padding:12px 24px;border-radius:4px;display:inline-block;font-weight:700;">Descargar PDF (47 puntos)</a>'
        . '</p>'
        . '<p style="font-size:13px;color:#6b7280;">El enlace es válido hasta el <strong>' . esc_html($expires_human) . '</strong>.</p>'
        . '<p>Si tienes una subasta concreta en el radar y quieres un análisis personalizado, podemos elaborarte un <strong>informe jurídico previo</strong> por <strong>72,60&nbsp;€</strong> con entrega en 48&nbsp;h.</p>'
        . '<p><a href="' . esc_url(home_url('/informe-juridico-subasta')) . '" style="color:#2563eb;">Más información sobre el informe jurídico →</a></p>'
        . '<p style="margin-top:32px;font-size:12px;color:#9ca3af;">Has recibido este correo porque solicitaste el checklist en comprarensubasta.com. Puedes ejercer tus derechos de acceso, rectificación y supresión escribiendo a info@cafave.com.</p>';

    $subject = 'Tu Checklist 47 puntos — CAFAVE Investment';
    $headers = ['Content-Type: text/html; charset=UTF-8', 'From: CAFAVE Investment <noreply@' . parse_url(home_url(), PHP_URL_HOST) . '>'];
    wp_mail($email, $subject, cafave_lm_brand_email_wrap('Tu checklist está listo', $body), $headers);

    // Aviso interno (opcional)
    do_action('cafave_lm_new_lead', ['email' => $email, 'nombre' => $nombre, 'source' => 'checklist']);

    return new WP_REST_Response([
        'ok' => true,
        'message' => 'Te hemos enviado el enlace de descarga a tu email.',
    ], 200);
}

function cafave_lm_handle_checklist_download(WP_REST_Request $req) {
    $token = sanitize_text_field((string) $req->get_param('token'));
    if (empty($token)) {
        return new WP_Error('missing_token', 'Token requerido', ['status' => 400]);
    }

    global $wpdb;
    $table = $wpdb->prefix . 'cafave_leads';
    $row = $wpdb->get_row($wpdb->prepare(
        "SELECT id, email, token_expires_at FROM $table WHERE download_token = %s LIMIT 1",
        $token
    ));

    if (!$row) {
        return new WP_Error('invalid_token', 'Enlace no válido', ['status' => 404]);
    }
    if (strtotime($row->token_expires_at) < time()) {
        return new WP_Error('expired_token', 'Enlace caducado. Solicítalo de nuevo.', ['status' => 410]);
    }

    $pdf = cafave_lm_pdf_path();
    if (!file_exists($pdf)) {
        return new WP_Error('pdf_missing', 'PDF no disponible. Contacta con soporte.', ['status' => 500]);
    }

    // Marcar descarga
    $wpdb->query($wpdb->prepare(
        "UPDATE $table SET downloaded_at = NOW(), download_count = download_count + 1 WHERE id = %d",
        $row->id
    ));

    // Stream PDF
    nocache_headers();
    header('Content-Type: application/pdf');
    header('Content-Disposition: attachment; filename="checklist-47-puntos-cafave.pdf"');
    header('Content-Length: ' . filesize($pdf));
    readfile($pdf);
    exit;
}

// ──────────────────────────────
//  NEWSLETTER: alta + doble opt-in
// ──────────────────────────────

function cafave_lm_handle_newsletter_subscribe(WP_REST_Request $req) {
    $ip = cafave_lm_client_ip();
    if (cafave_lm_rate_limited($ip)) {
        return new WP_Error('rate_limited', 'Demasiadas peticiones', ['status' => 429]);
    }
    if (!empty(trim((string) $req->get_param('website')))) {
        return new WP_REST_Response(['ok' => true], 200);
    }

    $email           = sanitize_email((string) $req->get_param('email'));
    $provincia_pref  = sanitize_text_field((string) $req->get_param('provincia'));
    $consent         = $req->get_param('consent') ? 1 : 0;

    if (!cafave_lm_validate_email($email)) {
        return new WP_Error('invalid_email', 'Email inválido', ['status' => 400]);
    }
    if (!$consent) {
        return new WP_Error('no_consent', 'Debes aceptar la política de privacidad', ['status' => 400]);
    }
    if ($provincia_pref !== '' && !preg_match('/^\d{2}$/', $provincia_pref)) {
        $provincia_pref = null;
    }

    global $wpdb;
    $table = $wpdb->prefix . 'cafave_subscribers';

    $existing = $wpdb->get_row($wpdb->prepare(
        "SELECT id, status, unsubscribe_token FROM $table WHERE email = %s LIMIT 1",
        $email
    ));

    if ($existing && $existing->status === 'active') {
        return new WP_REST_Response([
            'ok' => true,
            'message' => 'Ya estás suscrito. ¡Gracias!',
        ], 200);
    }

    $confirm_token     = cafave_lm_generate_token();
    $unsubscribe_token = $existing ? $existing->unsubscribe_token : cafave_lm_generate_token();
    $confirm_expires   = gmdate('Y-m-d H:i:s', time() + CAFAVE_LM_CONFIRM_TOKEN_TTL);

    if ($existing) {
        $wpdb->update(
            $table,
            [
                'provincia_pref'     => $provincia_pref,
                'status'             => 'pending',
                'confirm_token'      => $confirm_token,
                'confirm_expires_at' => $confirm_expires,
                'consentimiento_rgpd'=> 1,
                'ip_origen'          => $ip,
            ],
            ['id' => $existing->id]
        );
    } else {
        $wpdb->insert($table, [
            'email'              => $email,
            'provincia_pref'     => $provincia_pref,
            'status'             => 'pending',
            'confirm_token'      => $confirm_token,
            'confirm_expires_at' => $confirm_expires,
            'unsubscribe_token'  => $unsubscribe_token,
            'consentimiento_rgpd'=> 1,
            'ip_origen'          => $ip,
        ]);
    }

    $confirm_url = rest_url(CAFAVE_LM_NAMESPACE . '/newsletter/confirm') . '?token=' . urlencode($confirm_token);
    $body = '<p>Hola,</p>'
        . '<p>Para activar tu suscripción a <strong>Subastas BOE de la semana</strong>, confirma tu email haciendo clic abajo:</p>'
        . '<p style="text-align:center;margin:24px 0;">'
        .   '<a href="' . esc_url($confirm_url) . '" style="background:#2563eb;color:#fff;text-decoration:none;padding:12px 24px;border-radius:4px;display:inline-block;font-weight:700;">Confirmar mi suscripción</a>'
        . '</p>'
        . '<p style="font-size:13px;color:#6b7280;">Cada lunes recibirás las 10 mejores subastas judiciales publicadas en el BOE, con comentario jurídico de nuestro equipo.</p>'
        . '<p style="font-size:12px;color:#9ca3af;">Si no has solicitado esta suscripción, ignora este correo. Tus datos no se conservarán.</p>';

    $subject = 'Confirma tu suscripción — CAFAVE Investment';
    $headers = ['Content-Type: text/html; charset=UTF-8', 'From: CAFAVE Investment <noreply@' . parse_url(home_url(), PHP_URL_HOST) . '>'];
    wp_mail($email, $subject, cafave_lm_brand_email_wrap('Un paso más', $body), $headers);

    return new WP_REST_Response([
        'ok' => true,
        'message' => 'Te hemos enviado un email para confirmar tu suscripción.',
    ], 200);
}

function cafave_lm_handle_newsletter_confirm(WP_REST_Request $req) {
    $token = sanitize_text_field((string) $req->get_param('token'));
    if (empty($token)) {
        return cafave_lm_html_response('Enlace no válido', 'El enlace de confirmación no es válido.', 400);
    }
    global $wpdb;
    $table = $wpdb->prefix . 'cafave_subscribers';
    $row = $wpdb->get_row($wpdb->prepare(
        "SELECT id, status, confirm_expires_at FROM $table WHERE confirm_token = %s LIMIT 1",
        $token
    ));

    if (!$row) {
        return cafave_lm_html_response('Enlace no válido', 'Este enlace no corresponde a ninguna suscripción.', 404);
    }
    if (strtotime($row->confirm_expires_at) < time()) {
        return cafave_lm_html_response('Enlace caducado', 'El enlace de confirmación ha caducado. Vuelve a suscribirte.', 410);
    }
    if ($row->status === 'active') {
        return cafave_lm_html_response('Ya estabas suscrito', 'Tu suscripción ya estaba activa. ¡Hasta el próximo lunes!', 200);
    }

    $wpdb->update(
        $table,
        ['status' => 'active', 'fecha_confirm' => current_time('mysql'), 'confirm_token' => null],
        ['id' => $row->id]
    );

    return cafave_lm_html_response(
        '¡Suscripción confirmada!',
        '<p>Tu suscripción está activa. Cada lunes a las 9:00 recibirás las 10 mejores subastas judiciales con comentario jurídico.</p>'
        . '<p><a href="' . esc_url(home_url()) . '" style="color:#2563eb;">Volver al inicio →</a></p>',
        200
    );
}

function cafave_lm_handle_newsletter_unsubscribe(WP_REST_Request $req) {
    $token = sanitize_text_field((string) $req->get_param('token'));
    if (empty($token)) {
        return cafave_lm_html_response('Enlace no válido', 'Falta el token de baja.', 400);
    }
    global $wpdb;
    $table = $wpdb->prefix . 'cafave_subscribers';
    $row = $wpdb->get_row($wpdb->prepare(
        "SELECT id, status FROM $table WHERE unsubscribe_token = %s LIMIT 1",
        $token
    ));

    if (!$row) {
        return cafave_lm_html_response('Enlace no válido', 'No encontramos tu suscripción.', 404);
    }
    if ($row->status === 'unsubscribed') {
        return cafave_lm_html_response('Ya estabas dado de baja', 'No volverás a recibir más correos. Si fue un error, vuelve a suscribirte.', 200);
    }

    $wpdb->update(
        $table,
        ['status' => 'unsubscribed', 'fecha_baja' => current_time('mysql')],
        ['id' => $row->id]
    );

    return cafave_lm_html_response(
        'Te has dado de baja',
        '<p>Lamentamos verte ir. No volverás a recibir nuestra newsletter.</p>'
        . '<p>Si quieres volver, suscríbete de nuevo en <a href="' . esc_url(home_url()) . '" style="color:#2563eb;">comprarensubasta.com</a>.</p>',
        200
    );
}

function cafave_lm_handle_list_subscribers(WP_REST_Request $req) {
    global $wpdb;
    $table = $wpdb->prefix . 'cafave_subscribers';
    $rows = $wpdb->get_results(
        "SELECT id, email, provincia_pref, unsubscribe_token, fecha_confirm
         FROM $table
         WHERE status = 'active'
         ORDER BY id ASC",
        ARRAY_A
    );
    return new WP_REST_Response(['subscribers' => $rows, 'count' => count($rows)], 200);
}

function cafave_lm_html_response(string $title, string $message, int $status) {
    // El REST API serializa a JSON por defecto; salimos directo con HTML.
    nocache_headers();
    status_header($status);
    header('Content-Type: text/html; charset=UTF-8');
    echo '<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>', esc_html($title), '</title>',
        '<style>body{font-family:Helvetica,Arial,sans-serif;background:#f3f4f6;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;color:#1f2937}.box{max-width:480px;background:#fff;padding:36px;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.06);text-align:center}.brand{font-size:11px;letter-spacing:3px;color:#2563eb;text-transform:uppercase;margin-bottom:16px}h1{color:#0f1e3a;font-size:22px;margin:0 0 12px}p{line-height:1.6;color:#475569;margin:0 0 12px}a{color:#2563eb;text-decoration:none}</style>',
        '</head><body><div class="box"><div class="brand">CAFAVE INVESTMENT</div><h1>', esc_html($title), '</h1>', $message, '</div></body></html>';
    exit;
}

// ════════════════════════════════════════════════════════════════
//  SHORTCODES
// ════════════════════════════════════════════════════════════════

function cafave_lm_provincias_options(): string {
    $list = [
        '01'=>'Álava','02'=>'Albacete','03'=>'Alicante','04'=>'Almería','05'=>'Ávila',
        '06'=>'Badajoz','07'=>'Baleares','08'=>'Barcelona','09'=>'Burgos','10'=>'Cáceres',
        '11'=>'Cádiz','12'=>'Castellón','13'=>'Ciudad Real','14'=>'Córdoba','15'=>'A Coruña',
        '16'=>'Cuenca','17'=>'Girona','18'=>'Granada','19'=>'Guadalajara','20'=>'Guipúzcoa',
        '21'=>'Huelva','22'=>'Huesca','23'=>'Jaén','24'=>'León','25'=>'Lleida',
        '26'=>'La Rioja','27'=>'Lugo','28'=>'Madrid','29'=>'Málaga','30'=>'Murcia',
        '31'=>'Navarra','32'=>'Ourense','33'=>'Asturias','34'=>'Palencia','35'=>'Las Palmas',
        '36'=>'Pontevedra','37'=>'Salamanca','38'=>'Santa Cruz de Tenerife','39'=>'Cantabria',
        '40'=>'Segovia','41'=>'Sevilla','42'=>'Soria','43'=>'Tarragona','44'=>'Teruel',
        '45'=>'Toledo','46'=>'Valencia','47'=>'Valladolid','48'=>'Vizcaya','49'=>'Zamora',
        '50'=>'Zaragoza','51'=>'Ceuta','52'=>'Melilla',
    ];
    $out = '<option value="">Todas las provincias</option>';
    foreach ($list as $code => $name) {
        $out .= '<option value="' . esc_attr($code) . '">' . esc_html($name) . '</option>';
    }
    return $out;
}

function cafave_lm_form_css(): string {
    static $printed = false;
    if ($printed) return '';
    $printed = true;
    return '<style>
    .cafave-lm-form{max-width:520px;margin:0 auto;font-family:inherit;color:#1f2937;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.04)}
    .cafave-lm-form h3{color:#0f1e3a;margin:0 0 6px;font-size:20px}
    .cafave-lm-form .lead{color:#475569;font-size:14px;margin:0 0 18px}
    .cafave-lm-form label{display:block;font-size:13px;font-weight:600;color:#374151;margin:10px 0 4px}
    .cafave-lm-form input[type=text],.cafave-lm-form input[type=email],.cafave-lm-form select{width:100%;padding:10px 12px;border:1px solid #d1d5db;border-radius:4px;font-size:15px;box-sizing:border-box;background:#fff}
    .cafave-lm-form input[type=text]:focus,.cafave-lm-form input[type=email]:focus,.cafave-lm-form select:focus{outline:none;border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,0.15)}
    .cafave-lm-form .check{display:flex;align-items:flex-start;gap:8px;margin:14px 0 6px;font-size:13px;color:#475569;line-height:1.45}
    .cafave-lm-form .check input{flex-shrink:0;margin-top:2px}
    .cafave-lm-form .check a{color:#2563eb}
    .cafave-lm-form button{width:100%;background:#2563eb;color:#fff;border:0;padding:12px 16px;border-radius:4px;font-size:15px;font-weight:700;cursor:pointer;margin-top:14px;transition:background .15s}
    .cafave-lm-form button:hover{background:#1d4ed8}
    .cafave-lm-form button:disabled{background:#94a3b8;cursor:not-allowed}
    .cafave-lm-form .msg{margin-top:14px;padding:10px 12px;border-radius:4px;font-size:14px;display:none}
    .cafave-lm-form .msg.ok{display:block;background:#ecfdf5;border:1px solid #a7f3d0;color:#065f46}
    .cafave-lm-form .msg.err{display:block;background:#fef2f2;border:1px solid #fecaca;color:#991b1b}
    .cafave-lm-form .hp{position:absolute;left:-9999px;width:1px;height:1px}
    .cafave-lm-banner{max-width:340px;background:linear-gradient(180deg,#0f1e3a 0%,#1d3b6e 100%);color:#fff;padding:22px 20px;border-radius:8px}
    .cafave-lm-banner .brand{font-size:10px;letter-spacing:3px;color:#93c5fd;text-transform:uppercase;margin-bottom:8px}
    .cafave-lm-banner h4{color:#fff;margin:0 0 8px;font-size:18px;line-height:1.25}
    .cafave-lm-banner p{color:#cbd5e1;font-size:13px;margin:0 0 14px;line-height:1.5}
    .cafave-lm-banner a{display:inline-block;background:#2563eb;color:#fff;padding:9px 16px;border-radius:4px;font-weight:700;text-decoration:none;font-size:14px}
    </style>';
}

function cafave_lm_form_js(): string {
    static $printed = false;
    if ($printed) return '';
    $printed = true;
    $rest_root = esc_js(rest_url(CAFAVE_LM_NAMESPACE . '/'));
    return "<script>
    (function(){
      function submit(form, endpoint){
        var btn = form.querySelector('button');
        var msg = form.querySelector('.msg');
        msg.className = 'msg'; msg.textContent = '';
        btn.disabled = true; btn.dataset.label = btn.textContent; btn.textContent = 'Enviando…';
        var data = new FormData(form);
        var payload = {};
        data.forEach(function(v,k){ payload[k] = v; });
        fetch('{$rest_root}' + endpoint, {
          method: 'POST',
          headers: {'Content-Type':'application/json','Accept':'application/json'},
          body: JSON.stringify(payload)
        }).then(function(r){ return r.json().then(function(j){ return {ok:r.ok,j:j}; }); })
        .then(function(res){
          if(res.ok && res.j.ok){
            msg.className = 'msg ok'; msg.textContent = res.j.message || '¡Gracias! Revisa tu email.';
            form.reset();
          } else {
            msg.className = 'msg err'; msg.textContent = (res.j && res.j.message) || (res.j && res.j.data && res.j.data.status === 429 ? 'Demasiadas peticiones. Espera unos minutos.' : 'Ha ocurrido un error. Revisa los datos e inténtalo de nuevo.');
          }
        }).catch(function(){
          msg.className = 'msg err'; msg.textContent = 'No hemos podido enviar el formulario. Inténtalo más tarde.';
        }).finally(function(){
          btn.disabled = false; btn.textContent = btn.dataset.label;
        });
      }
      document.addEventListener('submit', function(e){
        if(e.target.matches('.cafave-lm-form[data-endpoint]')){
          e.preventDefault();
          submit(e.target, e.target.dataset.endpoint);
        }
      });
    })();
    </script>";
}

add_shortcode('cafave_checklist_form', function ($atts) {
    $atts = shortcode_atts(['title' => 'Descarga gratis el Checklist 47 puntos', 'lead' => 'Las verificaciones jurídicas que un equipo profesional realiza antes de pujar en una subasta del BOE. PDF de 8 páginas, gratuito.'], $atts, 'cafave_checklist_form');
    $privacy_url = home_url('/aviso-legal');
    ob_start();
    echo cafave_lm_form_css();
    echo cafave_lm_form_js();
    ?>
    <form class="cafave-lm-form" data-endpoint="leads/checklist" autocomplete="off">
      <h3><?php echo esc_html($atts['title']); ?></h3>
      <p class="lead"><?php echo esc_html($atts['lead']); ?></p>
      <input type="text" name="website" class="hp" tabindex="-1" autocomplete="off">
      <label for="cafave-cl-nombre">Nombre</label>
      <input id="cafave-cl-nombre" type="text" name="nombre" required maxlength="100">
      <label for="cafave-cl-email">Email</label>
      <input id="cafave-cl-email" type="email" name="email" required maxlength="190">
      <label class="check">
        <input type="checkbox" name="interesado_informes" value="1">
        <span>Quiero recibir también informes jurídicos sobre subastas concretas (puntuales, sin compromiso).</span>
      </label>
      <label class="check">
        <input type="checkbox" name="consent" value="1" required>
        <span>He leído y acepto el <a href="<?php echo esc_url($privacy_url); ?>" target="_blank">aviso legal y la política de privacidad</a>, y consiento el tratamiento de mis datos por CAFAVE Investment para enviarme el checklist solicitado.</span>
      </label>
      <button type="submit">Recibir el checklist gratuito</button>
      <div class="msg" role="status" aria-live="polite"></div>
    </form>
    <?php
    return ob_get_clean();
});

add_shortcode('cafave_newsletter_form', function ($atts) {
    $atts = shortcode_atts(['title' => 'Recibe gratis cada lunes las 10 mejores subastas del BOE', 'lead' => 'Selección curada de oportunidades de inversión con comentario jurídico. Cancela cuando quieras.'], $atts, 'cafave_newsletter_form');
    $privacy_url = home_url('/aviso-legal');
    ob_start();
    echo cafave_lm_form_css();
    echo cafave_lm_form_js();
    ?>
    <form class="cafave-lm-form" data-endpoint="newsletter/subscribe" autocomplete="off">
      <h3><?php echo esc_html($atts['title']); ?></h3>
      <p class="lead"><?php echo esc_html($atts['lead']); ?></p>
      <input type="text" name="website" class="hp" tabindex="-1" autocomplete="off">
      <label for="cafave-nl-email">Email</label>
      <input id="cafave-nl-email" type="email" name="email" required maxlength="190">
      <label for="cafave-nl-provincia">Provincia de interés (opcional)</label>
      <select id="cafave-nl-provincia" name="provincia">
        <?php echo cafave_lm_provincias_options(); ?>
      </select>
      <label class="check">
        <input type="checkbox" name="consent" value="1" required>
        <span>He leído y acepto el <a href="<?php echo esc_url($privacy_url); ?>" target="_blank">aviso legal y la política de privacidad</a>, y consiento recibir comunicaciones comerciales semanales de CAFAVE Investment.</span>
      </label>
      <button type="submit">Suscribirme gratis</button>
      <div class="msg" role="status" aria-live="polite"></div>
    </form>
    <?php
    return ob_get_clean();
});

add_shortcode('cafave_checklist_banner', function ($atts) {
    $atts = shortcode_atts(['url' => '/recursos/checklist-47-puntos'], $atts, 'cafave_checklist_banner');
    ob_start();
    echo cafave_lm_form_css();
    ?>
    <aside class="cafave-lm-banner">
      <div class="brand">CAFAVE · Recurso gratuito</div>
      <h4>47 puntos a verificar antes de pujar</h4>
      <p>El checklist jurídico que usamos antes de autorizar una puja. PDF de 8 páginas, descarga inmediata.</p>
      <a href="<?php echo esc_url($atts['url']); ?>">Descargar gratis →</a>
    </aside>
    <?php
    return ob_get_clean();
});
