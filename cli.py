#!/usr/bin/env python3
"""
CLI para el sistema de automatización de subastas BOE.

Uso:
    python cli.py sync [--provincia CODIGO] [--force] [--dry-run]
    python cli.py status
    python cli.py test
    python cli.py report [--days N]
"""
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

import click
from datetime import datetime, timedelta

from config import settings
from config.provinces import PROVINCIAS_ANDALUCIA, PROVINCIAS_ESPANA, get_provincia_nombre
from src.utils.logger import setup_logger


# Configurar logging para CLI
logger = setup_logger('cli')


@click.group()
@click.version_option(version='1.0.0', prog_name='subastas-boe')
def cli():
    """Sistema de automatización de subastas BOE para WordPress."""
    pass


@cli.command()
@click.option('--provincia', '-p', default=None,
              help='Código de provincia (ej: 41 para Sevilla)')
@click.option('--force', '-f', is_flag=True,
              help='Forzar actualización incluso sin cambios')
@click.option('--dry-run', is_flag=True,
              help='Simular sin guardar ni publicar')
@click.option('--limit', '-l', type=int, default=None,
              help='Limitar número de subastas por provincia')
@click.option('--no-publish', is_flag=True,
              help='No publicar en WordPress')
def sync(provincia, force, dry_run, limit, no_publish):
    """
    Sincronizar subastas del BOE.

    Ejemplos:
        python cli.py sync                    # Todas las provincias
        python cli.py sync -p 41              # Solo Sevilla
        python cli.py sync --force            # Forzar actualización
        python cli.py sync --dry-run          # Modo simulación
        python cli.py sync --limit 5          # Limitar a 5 por provincia
    """
    click.echo("=" * 60)
    click.echo("SINCRONIZACIÓN DE SUBASTAS BOE")
    click.echo("=" * 60)

    if dry_run:
        click.secho("MODO DRY-RUN: No se guardarán cambios", fg='yellow')

    if provincia:
        nombre = get_provincia_nombre(provincia)
        click.echo(f"Provincia: {nombre} ({provincia})")
    else:
        click.echo(f"Provincias: {', '.join(settings.PROVINCIAS_CODIGOS)}")

    if limit:
        click.echo(f"Límite: {limit} subastas por provincia")

    click.echo("-" * 60)

    from main import run_sync

    try:
        results = run_sync(
            provincia=provincia,
            force=force,
            dry_run=dry_run,
            limit=limit,
            publish=not no_publish
        )

        # Mostrar resumen
        click.echo("\n" + "=" * 60)
        click.echo("RESUMEN")
        click.echo("=" * 60)

        total_encontradas = 0
        total_nuevas = 0
        total_publicadas = 0
        total_errores = 0

        for cod, stats in results.items():
            nombre = get_provincia_nombre(cod)
            click.echo(f"{nombre}: {stats.encontradas} encontradas, "
                      f"{stats.nuevas} nuevas, {stats.publicadas} publicadas")
            total_encontradas += stats.encontradas
            total_nuevas += stats.nuevas
            total_publicadas += stats.publicadas
            total_errores += stats.errores

        click.echo("-" * 60)
        click.echo(f"TOTAL: {total_encontradas} encontradas, "
                  f"{total_nuevas} nuevas, {total_publicadas} publicadas, "
                  f"{total_errores} errores")

        if total_errores > 0:
            click.secho(f"⚠️  Se produjeron {total_errores} errores", fg='yellow')

        click.secho("✅ Sincronización completada", fg='green')

    except Exception as e:
        click.secho(f"❌ Error: {e}", fg='red')
        raise SystemExit(1)


@cli.command()
def status():
    """
    Mostrar estado actual del sistema.

    Muestra información sobre:
        - Configuración
        - Estadísticas de base de datos
        - Última sincronización
    """
    click.echo("=" * 60)
    click.echo("ESTADO DEL SISTEMA")
    click.echo("=" * 60)

    from main import get_status

    try:
        status = get_status()

        click.echo("\n📋 Configuración:")
        click.echo(f"   WordPress URL: {status['config']['wp_url']}")
        click.echo(f"   Provincias: {', '.join(status['config']['provincias'])}")
        click.echo(f"   Modo headless: {status['config']['headless']}")

        click.echo("\n📊 Base de datos:")
        db = status['database']
        if 'error' in db:
            click.secho(f"   Error: {db['error']}", fg='red')
        else:
            click.echo(f"   Total subastas: {db.get('total_subastas', 0)}")
            click.echo(f"   Subastas activas: {db.get('subastas_activas', 0)}")
            click.echo(f"   Publicadas en WP: {db.get('subastas_publicadas', 0)}")
            click.echo(f"   Total bienes: {db.get('total_bienes', 0)}")

            if db.get('por_provincia'):
                click.echo("\n   Por provincia:")
                for cod, count in db['por_provincia'].items():
                    nombre = get_provincia_nombre(cod)
                    click.echo(f"      {nombre}: {count} bienes")

        click.secho("\n✅ Sistema operativo", fg='green')

    except Exception as e:
        click.secho(f"❌ Error obteniendo estado: {e}", fg='red')


@cli.command()
@click.option('--wordpress', '-w', is_flag=True, help='Solo probar WordPress')
@click.option('--boe', '-b', is_flag=True, help='Solo probar BOE')
@click.option('--database', '-d', is_flag=True, help='Solo probar base de datos')
def test(wordpress, boe, database):
    """
    Probar conexiones del sistema.

    Ejemplos:
        python cli.py test              # Probar todas las conexiones
        python cli.py test --wordpress  # Solo WordPress
        python cli.py test --boe        # Solo BOE
    """
    click.echo("=" * 60)
    click.echo("PRUEBA DE CONEXIONES")
    click.echo("=" * 60)

    # Si no se especifica ninguna, probar todas
    test_all = not (wordpress or boe or database)

    from main import test_connections

    results = {}

    if test_all or boe:
        click.echo("\n🔍 Probando conexión al BOE...")
        from src.scraper.boe_scraper import BOEScraper
        try:
            with BOEScraper(headless=True) as scraper:
                results['boe'] = scraper.verificar_conexion()
            if results['boe']:
                click.secho("   ✅ BOE: Conexión exitosa", fg='green')
            else:
                click.secho("   ❌ BOE: Fallo en conexión", fg='red')
        except Exception as e:
            click.secho(f"   ❌ BOE: Error - {e}", fg='red')
            results['boe'] = False

    if test_all or wordpress:
        click.echo("\n🔍 Probando conexión a WordPress...")
        from src.wordpress.client import WordPressClient
        try:
            client = WordPressClient()
            results['wordpress'] = client.test_connection()
            if results['wordpress']:
                click.secho("   ✅ WordPress: Conexión exitosa", fg='green')
            else:
                click.secho("   ❌ WordPress: Fallo en autenticación", fg='red')
        except Exception as e:
            click.secho(f"   ❌ WordPress: Error - {e}", fg='red')
            results['wordpress'] = False

    if test_all or database:
        click.echo("\n🔍 Probando base de datos...")
        from src.models.database import Database
        try:
            db = Database(settings.DB_PATH)
            stats = db.get_estadisticas()
            db.close()
            results['database'] = True
            click.secho(f"   ✅ Base de datos: OK ({stats['total_subastas']} subastas)", fg='green')
        except Exception as e:
            click.secho(f"   ❌ Base de datos: Error - {e}", fg='red')
            results['database'] = False

    # Resumen
    click.echo("\n" + "-" * 60)
    all_ok = all(results.values()) if results else False
    if all_ok:
        click.secho("✅ Todas las pruebas pasaron correctamente", fg='green')
    else:
        click.secho("⚠️  Algunas pruebas fallaron", fg='yellow')


@cli.command()
@click.option('--days', '-d', type=int, default=7,
              help='Días a incluir en el reporte')
def report(days):
    """
    Generar reporte de actividad.

    Ejemplos:
        python cli.py report              # Últimos 7 días
        python cli.py report --days 30    # Último mes
    """
    click.echo("=" * 60)
    click.echo(f"REPORTE DE ACTIVIDAD (Últimos {days} días)")
    click.echo("=" * 60)

    from src.models.database import Database

    try:
        db = Database(settings.DB_PATH)
        stats = db.get_estadisticas()

        click.echo(f"\n📊 Estadísticas generales:")
        click.echo(f"   Total subastas en BD: {stats['total_subastas']}")
        click.echo(f"   Subastas activas: {stats['subastas_activas']}")
        click.echo(f"   Publicadas en WordPress: {stats['subastas_publicadas']}")

        click.echo(f"\n📍 Distribución por provincia:")
        for cod, count in stats.get('por_provincia', {}).items():
            nombre = get_provincia_nombre(cod)
            click.echo(f"   {nombre}: {count} bienes")

        db.close()

    except Exception as e:
        click.secho(f"❌ Error generando reporte: {e}", fg='red')


@cli.command()
@click.option('--dry-run', is_flag=True,
              help='Simular sin realizar cambios')
def cleanup(dry_run):
    """
    Verificar y despublicar subastas finalizadas o canceladas.

    Este comando:
    - Verifica el estado de todas las subastas publicadas
    - Detecta subastas finalizadas (por fecha o estado en BOE)
    - Detecta subastas canceladas (eliminadas del BOE)
    - Despublica los posts (pasa a borrador) y actualiza el estado

    Ejemplos:
        python cli.py cleanup              # Ejecutar limpieza
        python cli.py cleanup --dry-run    # Simular sin cambios
    """
    click.echo("=" * 60)
    click.echo("LIMPIEZA DE SUBASTAS FINALIZADAS/CANCELADAS")
    click.echo("=" * 60)

    if dry_run:
        click.secho("MODO DRY-RUN: No se realizarán cambios", fg='yellow')

    click.echo("-" * 60)

    from main import run_cleanup

    try:
        stats = run_cleanup(dry_run=dry_run)

        # Mostrar resumen
        click.echo("\n" + "=" * 60)
        click.echo("RESUMEN")
        click.echo("=" * 60)
        click.echo(f"Subastas verificadas: {stats.verificadas}")
        click.echo(f"Finalizadas: {stats.finalizadas}")
        click.echo(f"Canceladas: {stats.canceladas}")
        click.echo(f"Despublicadas: {stats.despublicadas}")
        click.echo(f"Errores: {stats.errores}")
        click.echo(f"Duración: {stats.duracion:.1f} segundos")

        if stats.despublicadas > 0:
            click.secho(f"✅ {stats.despublicadas} subastas despublicadas", fg='green')
        elif stats.verificadas > 0:
            click.secho("✅ Todas las subastas siguen activas", fg='green')
        else:
            click.echo("ℹ️  No hay subastas publicadas para verificar")

    except Exception as e:
        click.secho(f"❌ Error: {e}", fg='red')
        raise SystemExit(1)


@cli.command('init-db')
@click.option('--reset', is_flag=True, help='Eliminar y recrear tablas')
def init_db(reset):
    """
    Inicializar base de datos.

    Crea las tablas necesarias si no existen.
    Use --reset para eliminar datos existentes.
    """
    if reset:
        if not click.confirm('⚠️  Esto eliminará TODOS los datos. ¿Continuar?'):
            click.echo('Operación cancelada.')
            return

    click.echo("Inicializando base de datos...")

    from src.models.database import Database
    import os

    try:
        if reset and os.path.exists(settings.DB_PATH):
            os.remove(settings.DB_PATH)
            click.echo("Base de datos anterior eliminada.")

        db = Database(settings.DB_PATH)
        db.close()

        click.secho("✅ Base de datos inicializada correctamente", fg='green')

    except Exception as e:
        click.secho(f"❌ Error: {e}", fg='red')


@cli.command()
@click.argument('id_subasta')
@click.option('--update', '-u', is_flag=True, help='Actualizar si ya existe')
def publish(id_subasta, update):
    """
    Publicar una subasta específica en WordPress.

    Ejemplos:
        python cli.py publish SUB-JA-2025-249514
        python cli.py publish SUB-JA-2025-249514 --update
    """
    click.echo(f"Publicando subasta: {id_subasta}")

    from src.models.database import Database
    from src.wordpress.publisher import WordPressPublisher

    try:
        db = Database(settings.DB_PATH)
        subasta = db.get_subasta(id_subasta)

        if not subasta:
            click.secho(f"❌ Subasta {id_subasta} no encontrada en BD", fg='red')
            return

        publisher = WordPressPublisher()
        post_id = publisher.publish_subasta(subasta, update_if_exists=update)

        db.update_wp_post_id(id_subasta, post_id)
        db.close()

        click.secho(f"✅ Publicada correctamente. Post ID: {post_id}", fg='green')
        click.echo(f"   URL: {settings.WP_URL}/?p={post_id}")

    except Exception as e:
        click.secho(f"❌ Error publicando: {e}", fg='red')


@cli.command('social')
@click.argument('id_subasta')
@click.option('--platform', '-p', type=click.Choice(['all', 'instagram', 'facebook', 'twitter', 'linkedin']),
              default='all', help='Plataforma específica')
@click.option('--output', '-o', type=click.Path(), help='Guardar en archivo')
def social(id_subasta, platform, output):
    """
    Generar posts para redes sociales de una subasta.

    Ejemplos:
        python cli.py social SUB-JA-2025-249514
        python cli.py social SUB-JA-2025-249514 -p instagram
        python cli.py social SUB-JA-2025-249514 -o posts.txt
    """
    from src.models.database import Database
    from src.social.post_generator import SocialPostGenerator

    click.echo("=" * 60)
    click.echo("GENERADOR DE POSTS PARA REDES SOCIALES")
    click.echo("=" * 60)

    try:
        db = Database(settings.DB_PATH)
        subasta = db.get_subasta(id_subasta)
        db.close()

        if not subasta:
            click.secho(f"❌ Subasta {id_subasta} no encontrada en BD", fg='red')
            return

        generator = SocialPostGenerator()

        if platform == 'all':
            posts = generator.generate_all_platforms(subasta)
        else:
            method = getattr(generator, f'generate_{platform}')
            posts = {platform: method(subasta)}

        output_text = []

        for plat, post in posts.items():
            header = f"\n{'='*60}\n📱 {plat.upper()}\n{'='*60}"
            content = post.full_post()
            stats = f"\n📊 Caracteres: {post.character_count}\n🖼️ Imagen: {post.image_suggestion}"

            click.echo(header)
            click.echo(content)
            click.secho(stats, fg='cyan')

            output_text.append(f"{header}\n{content}\n{stats}")

        if output:
            with open(output, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(output_text))
            click.secho(f"\n✅ Posts guardados en: {output}", fg='green')

        click.secho("\n✅ Posts generados correctamente", fg='green')

    except Exception as e:
        click.secho(f"❌ Error: {e}", fg='red')


@cli.command('social-batch')
@click.option('--limit', '-l', type=int, default=5, help='Número de subastas')
@click.option('--output-dir', '-o', type=click.Path(), default='./social_posts',
              help='Directorio de salida')
def social_batch(limit, output_dir):
    """
    Generar posts para múltiples subastas activas.

    Ejemplos:
        python cli.py social-batch
        python cli.py social-batch --limit 10
        python cli.py social-batch -o ./mi_carpeta
    """
    import os
    from src.models.database import Database
    from src.social.post_generator import SocialPostGenerator

    click.echo("=" * 60)
    click.echo("GENERACIÓN MASIVA DE POSTS PARA REDES SOCIALES")
    click.echo("=" * 60)

    try:
        # Crear directorio si no existe
        os.makedirs(output_dir, exist_ok=True)

        db = Database(settings.DB_PATH)
        # Obtener subastas activas
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT id_subasta FROM subastas
            WHERE activa = 1
            ORDER BY fecha_conclusion ASC
            LIMIT ?
        """, (limit,))

        subastas_ids = [row['id_subasta'] for row in cursor.fetchall()]

        if not subastas_ids:
            click.secho("No hay subastas activas en la base de datos", fg='yellow')
            return

        click.echo(f"Generando posts para {len(subastas_ids)} subastas...\n")

        generator = SocialPostGenerator()

        for i, id_subasta in enumerate(subastas_ids, 1):
            subasta = db.get_subasta(id_subasta)
            if not subasta:
                continue

            click.echo(f"[{i}/{len(subastas_ids)}] {id_subasta}")

            posts = generator.generate_all_platforms(subasta)

            # Guardar archivo por subasta
            filename = os.path.join(output_dir, f"{id_subasta.replace('/', '-')}.txt")
            with open(filename, 'w', encoding='utf-8') as f:
                for plat, post in posts.items():
                    f.write(f"{'='*60}\n")
                    f.write(f"📱 {plat.upper()}\n")
                    f.write(f"{'='*60}\n")
                    f.write(post.full_post())
                    f.write(f"\n\n📊 Caracteres: {post.character_count}\n")
                    f.write(f"🖼️ Imagen: {post.image_suggestion}\n\n")

            click.secho(f"   ✅ {filename}", fg='green')

        db.close()

        click.echo("\n" + "=" * 60)
        click.secho(f"✅ Posts generados en: {output_dir}", fg='green')
        click.echo(f"   Total archivos: {len(subastas_ids)}")

    except Exception as e:
        click.secho(f"❌ Error: {e}", fg='red')


@cli.command('fix-categories')
@click.option('--dry-run', is_flag=True, help='Solo mostrar cambios sin aplicar')
@click.option('--update-db', is_flag=True, help='Actualizar provincia_codigo en BD')
@click.option('--update-pages', is_flag=True, help='Regenerar páginas de provincia en WP')
def fix_categories(dry_run, update_db, update_pages):
    """
    Corregir slugs de categorías de provincia en WordPress y BD.

    Ejemplos:
        python cli.py fix-categories --dry-run
        python cli.py fix-categories
        python cli.py fix-categories --update-db
        python cli.py fix-categories --update-pages
    """
    import requests
    import unicodedata

    click.echo("=" * 60)
    click.echo("CORRECCIÓN DE CATEGORÍAS DE PROVINCIA")
    click.echo("=" * 60)

    def normalize(s):
        nfkd = unicodedata.normalize('NFKD', s)
        return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

    # Construir mapa nombre→(código, slug_correcto)
    nombre_a_info = {}
    for codigo, data in PROVINCIAS_ESPANA.items():
        nombre_a_info[normalize(data["nombre"])] = (codigo, data["slug"])

    # Aliases BOE
    aliases = {
        "bizkaia": ("48", "vizcaya"),
        "gipuzkoa": ("20", "guipuzcoa"),
        "araba": ("01", "alava"),
        "illes balears": ("07", "baleares"),
    }
    nombre_a_info.update(aliases)

    def match_provincia(name):
        """Intenta resolver un nombre de categoría a (código, slug)."""
        key = normalize(name)
        if key in nombre_a_info:
            return nombre_a_info[key]
        # Probar partes de nombre bilingüe
        if '/' in name:
            for parte in name.split('/'):
                k = normalize(parte)
                if k in nombre_a_info:
                    return nombre_a_info[k]
        return None

    # ─── Paso 1: Corregir categorías en WordPress ───
    click.echo("\n📂 Buscando categorías en WordPress...")

    api_url = f"{settings.WP_URL}/wp-json/wp/v2"
    auth = (settings.WP_USER, settings.WP_APP_PASSWORD)

    # Obtener categoría padre "Subastas"
    resp = requests.get(f"{api_url}/categories", params={"slug": "subastas"})
    subastas_cats = resp.json() if resp.status_code == 200 else []
    parent_id = subastas_cats[0]["id"] if subastas_cats else None

    if not parent_id:
        click.secho("❌ No se encontró categoría padre 'Subastas'", fg='red')
        return

    # Obtener todas las categorías hijas
    all_cats = []
    page = 1
    while True:
        resp = requests.get(f"{api_url}/categories", params={
            "parent": parent_id, "per_page": 100, "page": page
        })
        if resp.status_code != 200:
            break
        batch = resp.json()
        if not batch:
            break
        all_cats.extend(batch)
        page += 1

    fixed = 0
    skipped = 0
    for cat in all_cats:
        match = match_provincia(cat["name"])
        if not match:
            click.echo(f"  ⚠️  No se pudo mapear: {cat['name']} (slug: {cat['slug']})")
            continue

        codigo, slug_correcto = match
        if cat["slug"] == slug_correcto:
            skipped += 1
            continue

        click.echo(f"  🔧 {cat['name']}: slug '{cat['slug']}' → '{slug_correcto}'")
        if not dry_run:
            resp = requests.post(
                f"{api_url}/categories/{cat['id']}",
                auth=auth,
                json={"slug": slug_correcto}
            )
            if resp.status_code == 200:
                fixed += 1
                click.secho(f"     ✅ Actualizado", fg='green')
            else:
                click.secho(f"     ❌ Error: {resp.status_code}", fg='red')
        else:
            fixed += 1

    prefix = "[DRY-RUN] " if dry_run else ""
    click.echo(f"\n{prefix}Categorías: {fixed} corregidas, {skipped} ya correctas")

    # ─── Paso 2: Actualizar provincia_codigo en BD ───
    if update_db:
        click.echo("\n💾 Actualizando provincia_codigo en BD...")
        from src.models.database import Database
        from src.scraper.parser import SubastaParser

        db = Database(settings.DB_PATH)
        conn = db.conn
        cursor = conn.execute(
            "SELECT DISTINCT provincia FROM bienes WHERE provincia IS NOT NULL AND (provincia_codigo IS NULL OR provincia_codigo = '')"
        )
        provincias_sin_codigo = [row[0] for row in cursor.fetchall()]

        updated_count = 0
        for prov_name in provincias_sin_codigo:
            codigo = SubastaParser._get_codigo_provincia(prov_name)
            if codigo:
                if not dry_run:
                    conn.execute(
                        "UPDATE bienes SET provincia_codigo = ? WHERE provincia = ? AND (provincia_codigo IS NULL OR provincia_codigo = '')",
                        (codigo, prov_name)
                    )
                    updated_count += conn.total_changes
                click.echo(f"  🔧 '{prov_name}' → código '{codigo}'")
            else:
                click.echo(f"  ⚠️  No se pudo resolver: '{prov_name}'")

        if not dry_run:
            conn.commit()
        db.close()
        click.echo(f"\n{prefix}BD: provincia_codigo actualizado para {len(provincias_sin_codigo)} provincias")

    # ─── Paso 3: Regenerar páginas de provincia ───
    if update_pages:
        click.echo("\n📄 Regenerando páginas de provincia...")
        from src.wordpress.page_generator import ProvinciaPageGenerator

        generator = ProvinciaPageGenerator()
        results = generator.create_all_pages()
        created = len([r for r in results if r['action'] == 'created'])
        updated_p = len([r for r in results if r['action'] == 'updated'])
        errors = len([r for r in results if r['action'] == 'error'])
        click.echo(f"\n  Páginas: {created} creadas, {updated_p} actualizadas, {errors} errores")

    click.echo("\n" + "=" * 60)
    click.secho("✅ Proceso completado", fg='green')


if __name__ == '__main__':
    cli()
