<?php
/**
 * Plugin Name: Subastas Meta API
 * Description: API REST de campos meta + autor CAFAVE + fechas en español + auto-respuesta al inversor (WPForms) + BBDD de inversores con exportación a Excel/CSV.
 * Version: 1.3
 * Author: CAFAVE INVESTMENT
 */

if (!defined('ABSPATH')) exit;

// Reply-To del correo automático al inversor: si el inversor responde, la respuesta va aquí.
if (!defined('SUBASTAS_REPLY_TO')) {
    define('SUBASTAS_REPLY_TO', 'pabloflores.abogado@outlook.com');
}

// ═══════════════════════════════════════════════════════════════
// REST API: exponer meta-campos de subastas
// ═══════════════════════════════════════════════════════════════

function subastas_meta_keys() {
    return array(
        '_subasta_id', '_subasta_tipo', '_subasta_estado', '_subasta_valor',
        '_subasta_deposito', '_subasta_fecha_inicio', '_subasta_fecha_fin',
        '_bien_tipo', '_bien_direccion', '_bien_localidad', '_bien_provincia', '_bien_cp',
    );
}

function subastas_register_meta_fields() {
    foreach (subastas_meta_keys() as $meta_key) {
        register_post_meta('post', $meta_key, array(
            'show_in_rest' => true,
            'single' => true,
            'type' => 'string',
            'auth_callback' => function() { return true; }
        ));
    }
}
add_action('init', 'subastas_register_meta_fields');

function subastas_add_meta_to_rest($response, $post, $request) {
    $meta_data = array();
    foreach (subastas_meta_keys() as $meta_key) {
        $value = get_post_meta($post->ID, $meta_key, true);
        $meta_data[$meta_key] = $value ? $value : '';
    }
    $response->data['subasta_meta'] = $meta_data;
    return $response;
}
add_filter('rest_prepare_post', 'subastas_add_meta_to_rest', 10, 3);

// ═══════════════════════════════════════════════════════════════
// Autor "CAFAVE INVESTMENT" en posts
// ═══════════════════════════════════════════════════════════════

function subastas_change_author_name($author_name) { return 'CAFAVE INVESTMENT'; }
add_filter('the_author', 'subastas_change_author_name');
add_filter('get_the_author_display_name', 'subastas_change_author_name');

function subastas_change_author_posts_link($link) {
    return preg_replace('/>[^<]+</', '>CAFAVE INVESTMENT<', $link);
}
add_filter('the_author_posts_link', 'subastas_change_author_posts_link');

// ═══════════════════════════════════════════════════════════════
// Formato de fecha español ("26 de enero de 2026")
// ═══════════════════════════════════════════════════════════════

function subastas_format_date_es($timestamp) {
    $meses = array(
        1 => 'enero', 2 => 'febrero', 3 => 'marzo', 4 => 'abril',
        5 => 'mayo', 6 => 'junio', 7 => 'julio', 8 => 'agosto',
        9 => 'septiembre', 10 => 'octubre', 11 => 'noviembre', 12 => 'diciembre'
    );
    return date('j', $timestamp) . ' de ' . $meses[(int) date('n', $timestamp)] . ' de ' . date('Y', $timestamp);
}

function subastas_fecha_espanol($fecha, $formato, $post) {
    return subastas_format_date_es(get_the_time('U', $post));
}
add_filter('get_the_date', 'subastas_fecha_espanol', 10, 3);

function subastas_the_date_espanol($fecha, $formato, $before, $after) {
    global $post;
    if (!$post) return $fecha;
    return $before . subastas_format_date_es(get_the_time('U', $post)) . $after;
}
add_filter('the_date', 'subastas_the_date_espanol', 10, 4);

// ═══════════════════════════════════════════════════════════════
// BBDD de inversores (tabla custom)
// El sitio usa WPForms Lite, que NO almacena envíos. Guardamos cada submission
// en wp_subastas_inversores para tener histórico + exportación a Excel.
// ═══════════════════════════════════════════════════════════════

function subastas_inv_table_name() {
    global $wpdb;
    return $wpdb->prefix . 'subastas_inversores';
}

function subastas_inv_ensure_table() {
    global $wpdb;
    $table = subastas_inv_table_name();
    $charset = $wpdb->get_charset_collate();

    $sql = "CREATE TABLE {$table} (
        id BIGINT(20) UNSIGNED NOT NULL AUTO_INCREMENT,
        created_at DATETIME NOT NULL,
        nombre VARCHAR(255) NOT NULL DEFAULT '',
        email VARCHAR(255) NOT NULL DEFAULT '',
        telefono VARCHAR(64) NOT NULL DEFAULT '',
        capital VARCHAR(64) NOT NULL DEFAULT '',
        subasta_id VARCHAR(64) NOT NULL DEFAULT '',
        tipo VARCHAR(128) NOT NULL DEFAULT '',
        localidad VARCHAR(128) NOT NULL DEFAULT '',
        provincia VARCHAR(128) NOT NULL DEFAULT '',
        form_id BIGINT(20) UNSIGNED NOT NULL DEFAULT 0,
        ip VARCHAR(45) NOT NULL DEFAULT '',
        PRIMARY KEY  (id),
        KEY email (email),
        KEY created_at (created_at),
        KEY provincia (provincia)
    ) {$charset};";

    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    dbDelta($sql);
}
register_activation_hook(__FILE__, 'subastas_inv_ensure_table');

// ═══════════════════════════════════════════════════════════════
// Helper: extraer datos de la subasta del HTTP_REFERER
// WPForms Lite no soporta hidden fields (es función Pro), así que parseamos
// la URL de la página donde el inversor envió el form. WPForms hace submit
// vía AJAX a /wp-admin/admin-ajax.php — el header Referer contiene la home
// con los query params del CTA intactos (?subasta=X&tipo=Y&localidad=Z&provincia=W).
// ═══════════════════════════════════════════════════════════════

function subastas_get_referer_params() {
    static $cache = null;
    if ($cache !== null) return $cache;

    $cache = array('subasta_id' => '', 'tipo' => '', 'localidad' => '', 'provincia' => '');
    $referer = isset($_SERVER['HTTP_REFERER']) ? (string) $_SERVER['HTTP_REFERER'] : '';
    if ($referer === '') return $cache;

    $parts = parse_url($referer);
    if (empty($parts['query'])) return $cache;

    parse_str($parts['query'], $q);
    if (!empty($q['subasta']))   $cache['subasta_id'] = sanitize_text_field($q['subasta']);
    if (!empty($q['tipo']))      $cache['tipo']       = sanitize_text_field($q['tipo']);
    if (!empty($q['localidad'])) $cache['localidad']  = sanitize_text_field($q['localidad']);
    if (!empty($q['provincia'])) $cache['provincia']  = sanitize_text_field($q['provincia']);

    return $cache;
}

// ═══════════════════════════════════════════════════════════════
// Smart Tags personalizados para usar en notificaciones de WPForms
// Se renderizan leyendo el HTTP_REFERER del envío del form.
// Tags disponibles: {subasta_id} {subasta_tipo} {subasta_localidad}
//                   {subasta_provincia} {subasta_url} {subasta_resumen}
// ═══════════════════════════════════════════════════════════════

function subastas_smart_tag_process($message, $form_data, $fields, $entry_id, $context) {
    if (strpos($message, '{subasta_') === false) {
        return $message;
    }
    $ref = subastas_get_referer_params();
    $url = ($ref['subasta_id'] !== '')
        ? 'https://comprarensubasta.com/?subasta=' . rawurlencode($ref['subasta_id'])
        : '';

    $resumen = '';
    if ($ref['subasta_id'] !== '') $resumen .= 'ID Subasta: ' . $ref['subasta_id'] . "\n";
    if ($ref['tipo'] !== '')       $resumen .= 'Tipo: ' . $ref['tipo'] . "\n";
    if ($ref['localidad'] !== '')  $resumen .= 'Localidad: ' . $ref['localidad'] . "\n";
    if ($ref['provincia'] !== '')  $resumen .= 'Provincia: ' . $ref['provincia'] . "\n";
    if ($url !== '')               $resumen .= 'URL: ' . $url . "\n";

    $replacements = array(
        '{subasta_id}'        => $ref['subasta_id'],
        '{subasta_tipo}'      => $ref['tipo'],
        '{subasta_localidad}' => $ref['localidad'],
        '{subasta_provincia}' => $ref['provincia'],
        '{subasta_url}'       => $url,
        '{subasta_resumen}'   => trim($resumen),
    );
    return str_replace(array_keys($replacements), array_values($replacements), $message);
}
add_filter('wpforms_process_smart_tags', 'subastas_smart_tag_process', 10, 5);

// ═══════════════════════════════════════════════════════════════
// Helper: extraer campos de una submission de WPForms
// ═══════════════════════════════════════════════════════════════

function subastas_extract_fields($fields) {
    $out = array(
        'email' => '', 'nombre' => '', 'telefono' => '', 'capital' => '',
        'subasta_id' => '', 'tipo' => '', 'localidad' => '', 'provincia' => '',
    );

    foreach ((array) $fields as $field) {
        if (!is_array($field)) continue;
        $name = isset($field['name']) ? strtolower((string) $field['name']) : '';
        $type = isset($field['type']) ? (string) $field['type'] : '';
        $value = isset($field['value']) ? trim((string) $field['value']) : '';
        if ($value === '') continue;

        // Si en el futuro se compra WPForms Pro y se añaden hidden fields, sus labels
        // se chequean primero porque coinciden exacto.
        if ($name === 'boe-subasta') {
            $out['subasta_id'] = sanitize_text_field($value);
        } elseif ($name === 'boe-tipo') {
            $out['tipo'] = sanitize_text_field($value);
        } elseif ($name === 'boe-localidad') {
            $out['localidad'] = sanitize_text_field($value);
        } elseif ($name === 'boe-provincia') {
            $out['provincia'] = sanitize_text_field($value);
        } elseif ($type === 'email' || strpos($name, 'email') !== false || strpos($name, 'correo') !== false) {
            $out['email'] = sanitize_email($value);
        } elseif ($type === 'phone' || strpos($name, 'tel') !== false || strpos($name, 'phone') !== false) {
            $out['telefono'] = sanitize_text_field($value);
        } elseif (strpos($name, 'capital') !== false) {
            $out['capital'] = sanitize_text_field($value);
        } elseif ($type === 'name' || strpos($name, 'nombre') !== false || strpos($name, 'razon') !== false || strpos($name, 'razón') !== false) {
            $out['nombre'] = sanitize_text_field($value);
        }
    }

    // Fallback: si los hidden fields no existen (WPForms Lite), tomamos los datos de la
    // URL desde la que se envió el form.
    $ref = subastas_get_referer_params();
    if ($out['subasta_id'] === '') $out['subasta_id'] = $ref['subasta_id'];
    if ($out['tipo'] === '')       $out['tipo']       = $ref['tipo'];
    if ($out['localidad'] === '')  $out['localidad']  = $ref['localidad'];
    if ($out['provincia'] === '')  $out['provincia']  = $ref['provincia'];

    return $out;
}

// ═══════════════════════════════════════════════════════════════
// Guardar submission en la BBDD (corre antes que la autorespuesta)
// ═══════════════════════════════════════════════════════════════

function subastas_inv_save_submission($fields, $entry, $form_data, $entry_id) {
    global $wpdb;
    subastas_inv_ensure_table();

    $data = subastas_extract_fields($fields);

    if (empty($data['email']) && empty($data['nombre'])) {
        return;
    }

    $wpdb->insert(subastas_inv_table_name(), array(
        'created_at' => current_time('mysql'),
        'nombre' => $data['nombre'],
        'email' => $data['email'],
        'telefono' => $data['telefono'],
        'capital' => $data['capital'],
        'subasta_id' => $data['subasta_id'],
        'tipo' => $data['tipo'],
        'localidad' => $data['localidad'],
        'provincia' => $data['provincia'],
        'form_id' => isset($form_data['id']) ? (int) $form_data['id'] : 0,
        'ip' => isset($_SERVER['REMOTE_ADDR']) ? substr(sanitize_text_field($_SERVER['REMOTE_ADDR']), 0, 45) : '',
    ));
}
add_action('wpforms_process_complete', 'subastas_inv_save_submission', 5, 4);

// ═══════════════════════════════════════════════════════════════
// Auto-respuesta CAFAVE al inversor (después de guardar en BBDD)
// ═══════════════════════════════════════════════════════════════

function subastas_wpforms_autoreply($fields, $entry, $form_data, $entry_id) {
    $data = subastas_extract_fields($fields);
    if (empty($data['email'])) return;

    $investor_email = $data['email'];
    $investor_name = $data['nombre'] !== '' ? $data['nombre'] : 'Inversor';
    $subasta_id = $data['subasta_id'];

    $subject = 'Información sobre su solicitud de soporte' . ($subasta_id ? ' - Subasta ' . $subasta_id : '');

    $body  = "Estimado " . $investor_name . ":\n\n";
    $body .= "Me dirijo a usted en mi condición de letrado de CAFAVE Investment, despacho especializado en la gestión técnica y jurídica de inversiones inmobiliarias mediante procedimientos de ejecución y subastas judiciales.\n\n";
    $body .= "Conocedores de su interés en la adquisición de activos a través de cauces judiciales, nos ponemos a su disposición para ofrecerle el soporte técnico necesario que garantice la seguridad jurídica de sus operaciones. En este sentido, le proponemos la elaboración de un Informe de Análisis Previo para el activo de su interés, cuyo objeto es mitigar los riesgos inherentes a este tipo de adquisiciones. Rogamos nos remita referencia de la Subasta para el análisis.\n\n";
    $body .= "El contenido pormenorizado de dicho dictamen comprenderá:\n\n";
    $body .= "Auditoría de cargas: Determinación del estado de cargas registrales y su prelación conforme a la Ley Hipotecaria y la LEC.\n\n";
    $body .= "Hoja de ruta procesal: Pasos preceptivos para la participación efectiva en el procedimiento de apremio.\n\n";
    $body .= "Proyección de costes: Estimación de los gastos operativos y fiscales asociados a la transmisión (ITP/AJD, honorarios, gastos de inscripción).\n\n";
    $body .= "Valoración pericial orientativa: Análisis del valor de mercado del inmueble para optimizar la puja.\n\n";
    $body .= "Condiciones económicas y formalización:\n\n";
    $body .= "El coste por la emisión del referido informe asciende a 60,00 € + IVA. Para proceder con el encargo y habilitar el estudio por parte de nuestro equipo, le ruego realice la transferencia bancaria a la cuenta que se detalla a continuación:\n\n";
    $body .= "Titular: Pablo Flores Avellaneda IBAN: ES18 2103 7842 9500 3012 6496 Concepto: Informe subasta " . ($subasta_id ? $subasta_id : "") . " – Importe: 72,60 € (IVA incluido)\n\n";
    $body .= "Una vez remitido el justificante de abono a esta dirección de correo, le haremos entrega del informe técnico en un plazo máximo de 24 horas hábiles.\n\n";
    $body .= "Nos pondremos en contacto con usted para evaluar sus necesidades.\n\n";
    $body .= "Quedo a su entera disposición para resolver cualquier duda técnica o concertar una breve llamada para profundizar en los detalles de nuestra colaboración.\n\n";
    $body .= "Atentamente,\n\n";
    $body .= "comprarensubasta.com\n\n";
    $body .= "Muchas Gracias.\n\n";
    $body .= "Reciba un cordial saludo.\n\n";
    $body .= "--CAFAVE ABOGADOS--\n\n";
    $body .= "Este correo y sus adjuntos son confidenciales y pueden contener información sujeta a secreto profesional. Si lo ha recibido por error, elimínelo y notifíquelo a CAFAVE INVESTMENT, SOCIEDAD LIMITADA(notificaciones@cafaveabogados.com). No asumimos responsabilidad por interceptaciones o daños informáticos. El contenido de este correo no constituye asesoramiento legal. Antes de imprimir, piense en el medio ambiente.";

    $headers = array(
        'Content-Type: text/plain; charset=UTF-8',
        'Reply-To: ' . SUBASTAS_REPLY_TO,
    );

    wp_mail($investor_email, $subject, $body, $headers);
}
add_action('wpforms_process_complete', 'subastas_wpforms_autoreply', 10, 4);

// ═══════════════════════════════════════════════════════════════
// Página admin: "Inversores CAFAVE"
// ═══════════════════════════════════════════════════════════════

function subastas_inv_admin_menu() {
    add_menu_page(
        'Inversores CAFAVE',
        'Inversores',
        'manage_options',
        'subastas-inversores',
        'subastas_inv_render_page',
        'dashicons-businessperson',
        25
    );
}
add_action('admin_menu', 'subastas_inv_admin_menu');

function subastas_inv_render_page() {
    if (!current_user_can('manage_options')) return;

    global $wpdb;
    subastas_inv_ensure_table();
    $table = subastas_inv_table_name();

    $rows = $wpdb->get_results("SELECT * FROM {$table} ORDER BY created_at DESC LIMIT 500", ARRAY_A);
    $count = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$table}");
    $export_url = wp_nonce_url(admin_url('admin-post.php?action=subastas_inv_export'), 'subastas_inv_export');

    echo '<div class="wrap">';
    echo '<h1>Inversores CAFAVE ';
    echo '<a href="' . esc_url($export_url) . '" class="page-title-action">Exportar a Excel/CSV</a>';
    echo '</h1>';
    echo '<p>Total registros: <strong>' . $count . '</strong>. Mostrando los 500 más recientes.</p>';
    echo '<table class="wp-list-table widefat fixed striped">';
    echo '<thead><tr>';
    foreach (array('Fecha', 'Nombre', 'Email', 'Teléfono', 'Capital', 'ID Subasta', 'Tipo', 'Localidad', 'Provincia') as $col) {
        echo '<th>' . esc_html($col) . '</th>';
    }
    echo '</tr></thead><tbody>';

    if (empty($rows)) {
        echo '<tr><td colspan="9">Aún no hay envíos. Los nuevos aparecerán aquí automáticamente.</td></tr>';
    } else {
        foreach ($rows as $r) {
            echo '<tr>';
            foreach (array('created_at', 'nombre', 'email', 'telefono', 'capital', 'subasta_id', 'tipo', 'localidad', 'provincia') as $k) {
                echo '<td>' . esc_html(isset($r[$k]) ? $r[$k] : '') . '</td>';
            }
            echo '</tr>';
        }
    }

    echo '</tbody></table></div>';
}

// ═══════════════════════════════════════════════════════════════
// Exportar a CSV (UTF-8 con BOM para que Excel lo abra en español)
// ═══════════════════════════════════════════════════════════════

function subastas_inv_export_csv() {
    if (!current_user_can('manage_options')) {
        wp_die('Sin permisos suficientes.');
    }
    check_admin_referer('subastas_inv_export');

    global $wpdb;
    subastas_inv_ensure_table();
    $table = subastas_inv_table_name();
    $rows = $wpdb->get_results("SELECT * FROM {$table} ORDER BY created_at DESC", ARRAY_A);

    $filename = 'inversores_cafave_' . date('Y-m-d_His') . '.csv';
    nocache_headers();
    header('Content-Type: text/csv; charset=UTF-8');
    header('Content-Disposition: attachment; filename="' . $filename . '"');

    $out = fopen('php://output', 'w');
    fwrite($out, "\xEF\xBB\xBF"); // BOM UTF-8 → Excel detecta acentos
    fputcsv($out, array('Fecha', 'Nombre', 'Email', 'Teléfono', 'Capital', 'ID Subasta', 'Tipo', 'Localidad', 'Provincia', 'Form ID', 'IP'));

    foreach ((array) $rows as $r) {
        fputcsv($out, array(
            isset($r['created_at']) ? $r['created_at'] : '',
            isset($r['nombre']) ? $r['nombre'] : '',
            isset($r['email']) ? $r['email'] : '',
            isset($r['telefono']) ? $r['telefono'] : '',
            isset($r['capital']) ? $r['capital'] : '',
            isset($r['subasta_id']) ? $r['subasta_id'] : '',
            isset($r['tipo']) ? $r['tipo'] : '',
            isset($r['localidad']) ? $r['localidad'] : '',
            isset($r['provincia']) ? $r['provincia'] : '',
            isset($r['form_id']) ? $r['form_id'] : '',
            isset($r['ip']) ? $r['ip'] : '',
        ));
    }
    fclose($out);
    exit;
}
add_action('admin_post_subastas_inv_export', 'subastas_inv_export_csv');
