<?php
/**
 * Plugin Name: Subastas Meta API
 * Description: Expone los campos meta de subastas en la API REST de WordPress
 * Version: 1.0
 * Author: CAFAVE INVESTMENT
 */

// Registrar campos meta para la API REST
function subastas_register_meta_fields() {
    $meta_fields = array(
        '_subasta_id',
        '_subasta_tipo',
        '_subasta_estado',
        '_subasta_valor',
        '_subasta_deposito',
        '_subasta_fecha_inicio',
        '_subasta_fecha_fin',
        '_bien_tipo',
        '_bien_direccion',
        '_bien_localidad',
        '_bien_provincia',
        '_bien_cp',
    );

    foreach ($meta_fields as $meta_key) {
        register_post_meta('post', $meta_key, array(
            'show_in_rest' => true,
            'single' => true,
            'type' => 'string',
            'auth_callback' => function() {
                return true; // Permitir lectura pública
            }
        ));
    }
}
add_action('init', 'subastas_register_meta_fields');

// Asegurar que los campos meta se incluyan en las respuestas REST
function subastas_add_meta_to_rest($response, $post, $request) {
    $meta_fields = array(
        '_subasta_id',
        '_subasta_tipo',
        '_subasta_estado',
        '_subasta_valor',
        '_subasta_deposito',
        '_subasta_fecha_inicio',
        '_subasta_fecha_fin',
        '_bien_tipo',
        '_bien_direccion',
        '_bien_localidad',
        '_bien_provincia',
        '_bien_cp',
    );

    $meta_data = array();
    foreach ($meta_fields as $meta_key) {
        $value = get_post_meta($post->ID, $meta_key, true);
        $meta_data[$meta_key] = $value ? $value : '';
    }

    $response->data['subasta_meta'] = $meta_data;
    return $response;
}
add_filter('rest_prepare_post', 'subastas_add_meta_to_rest', 10, 3);

// ═══════════════════════════════════════════════════════════════
// CORRECCIÓN 1: Cambiar nombre del autor a "CAFAVE INVESTMENT"
// ═══════════════════════════════════════════════════════════════

// Cambiar el nombre del autor mostrado en los posts
function subastas_change_author_name($author_name) {
    return 'CAFAVE INVESTMENT';
}
add_filter('the_author', 'subastas_change_author_name');
add_filter('get_the_author_display_name', 'subastas_change_author_name');

// También cambiar en los enlaces del autor
function subastas_change_author_posts_link($link) {
    return preg_replace('/>[^<]+</', '>CAFAVE INVESTMENT<', $link);
}
add_filter('the_author_posts_link', 'subastas_change_author_posts_link');

// ═══════════════════════════════════════════════════════════════
// CORRECCIÓN 2: Formato de fecha en español
// ═══════════════════════════════════════════════════════════════

// Forzar formato de fecha español: "26 de enero de 2026"
function subastas_fecha_espanol($fecha, $formato, $post) {
    $timestamp = get_the_time('U', $post);

    $meses = array(
        1 => 'enero', 2 => 'febrero', 3 => 'marzo', 4 => 'abril',
        5 => 'mayo', 6 => 'junio', 7 => 'julio', 8 => 'agosto',
        9 => 'septiembre', 10 => 'octubre', 11 => 'noviembre', 12 => 'diciembre'
    );

    $dia = date('j', $timestamp);
    $mes = $meses[(int)date('n', $timestamp)];
    $anio = date('Y', $timestamp);

    return $dia . ' de ' . $mes . ' de ' . $anio;
}
add_filter('get_the_date', 'subastas_fecha_espanol', 10, 3);

// También para the_date
function subastas_the_date_espanol($fecha, $formato, $before, $after) {
    global $post;
    if ($post) {
        $timestamp = get_the_time('U', $post);

        $meses = array(
            1 => 'enero', 2 => 'febrero', 3 => 'marzo', 4 => 'abril',
            5 => 'mayo', 6 => 'junio', 7 => 'julio', 8 => 'agosto',
            9 => 'septiembre', 10 => 'octubre', 11 => 'noviembre', 12 => 'diciembre'
        );

        $dia = date('j', $timestamp);
        $mes = $meses[(int)date('n', $timestamp)];
        $anio = date('Y', $timestamp);

        return $before . $dia . ' de ' . $mes . ' de ' . $anio . $after;
    }
    return $fecha;
}
add_filter('the_date', 'subastas_the_date_espanol', 10, 4);
