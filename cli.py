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
from config.provinces import PROVINCIAS_ANDALUCIA, get_provincia_nombre
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


if __name__ == '__main__':
    cli()
