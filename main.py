#!/usr/bin/env python3
"""
Sistema de automatización de subastas del BOE para WordPress.
Entry point principal.
"""
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional

from config import settings
from config.provinces import PROVINCIAS_ESPANA, get_provincia_nombre
from src.scraper.boe_scraper import BOEScraper
from src.models.database import Database
from src.wordpress.client import WordPressClient
from src.wordpress.publisher import WordPressPublisher
from src.utils.logger import setup_logger, get_sync_logger


logger = get_sync_logger()


class SyncStats:
    """Estadísticas de sincronización."""

    def __init__(self):
        self.encontradas = 0
        self.nuevas = 0
        self.actualizadas = 0
        self.publicadas = 0
        self.errores = 0
        self.start_time = datetime.now()

    @property
    def duracion(self) -> float:
        """Duración en segundos."""
        return (datetime.now() - self.start_time).total_seconds()

    def to_dict(self) -> dict:
        return {
            "encontradas": self.encontradas,
            "nuevas": self.nuevas,
            "actualizadas": self.actualizadas,
            "publicadas": self.publicadas,
            "errores": self.errores,
            "duracion_segundos": self.duracion,
        }

    def __str__(self) -> str:
        return (
            f"Encontradas: {self.encontradas}, "
            f"Nuevas: {self.nuevas}, "
            f"Actualizadas: {self.actualizadas}, "
            f"Publicadas: {self.publicadas}, "
            f"Errores: {self.errores}, "
            f"Duración: {self.duracion:.1f}s"
        )


def run_sync(
    provincia: str = None,
    force: bool = False,
    dry_run: bool = False,
    limit: int = None,
    publish: bool = True
) -> Dict[str, SyncStats]:
    """
    Ejecuta la sincronización de subastas.

    Args:
        provincia: Código de provincia específica (opcional)
        force: Forzar actualización incluso sin cambios
        dry_run: Simular sin guardar ni publicar
        limit: Límite de subastas por provincia
        publish: Si publicar en WordPress

    Returns:
        Diccionario con estadísticas por provincia
    """
    logger.info("=" * 60)
    logger.info("INICIANDO SINCRONIZACIÓN DE SUBASTAS BOE")
    logger.info("=" * 60)

    if dry_run:
        logger.info("MODO DRY-RUN: No se guardarán ni publicarán cambios")

    # Determinar provincias a procesar
    if provincia:
        provincias = {provincia: PROVINCIAS_ESPANA.get(provincia, {"nombre": provincia})}
    else:
        provincias = {cod: data for cod, data in PROVINCIAS_ESPANA.items()
                     if cod in settings.PROVINCIAS_CODIGOS}

    # Inicializar componentes
    db = Database(settings.DB_PATH) if not dry_run else None
    wp_client = WordPressClient() if publish and not dry_run else None
    wp_publisher = WordPressPublisher(wp_client) if wp_client else None

    results = {}
    total_stats = SyncStats()

    try:
        with BOEScraper(headless=settings.SELENIUM_HEADLESS) as scraper:
            for cod_provincia, data_provincia in provincias.items():
                nombre_provincia = data_provincia.get("nombre", cod_provincia)
                logger.info(f"\n{'='*40}")
                logger.info(f"Procesando: {nombre_provincia} ({cod_provincia})")
                logger.info(f"{'='*40}")

                stats = SyncStats()
                count = 0

                try:
                    for subasta_info in scraper.buscar_subastas(
                        provincia=cod_provincia,
                        tipo_bien="I",  # Inmuebles
                        estado="EJ"     # Celebrándose
                    ):
                        if limit and count >= limit:
                            logger.info(f"Alcanzado límite de {limit} subastas")
                            break

                        stats.encontradas += 1
                        id_subasta = subasta_info.get("id_subasta")

                        if not id_subasta:
                            continue

                        try:
                            # Verificar si existe
                            existe = db.subasta_existe(id_subasta) if db else False

                            if existe and not force:
                                # Verificar si hay cambios
                                existing = db.get_subasta(id_subasta)
                                # Por ahora, saltamos si ya existe
                                logger.debug(f"Subasta {id_subasta} ya existe, saltando")
                                continue

                            # Obtener detalle completo
                            logger.info(f"Extrayendo detalle: {id_subasta}")
                            subasta = scraper.get_detalle_subasta(id_subasta)

                            if not subasta:
                                logger.warning(f"No se pudo extraer detalle de {id_subasta}")
                                stats.errores += 1
                                continue

                            if not dry_run and db:
                                # Guardar en BD
                                if existe:
                                    db.update_subasta(subasta)
                                    stats.actualizadas += 1
                                    logger.info(f"Actualizada: {id_subasta}")
                                else:
                                    db.insert_subasta(subasta)
                                    stats.nuevas += 1
                                    logger.info(f"Nueva subasta: {id_subasta}")

                                # Publicar en WordPress
                                if wp_publisher:
                                    try:
                                        post_id = wp_publisher.publish_subasta(subasta)
                                        db.update_wp_post_id(id_subasta, post_id)
                                        stats.publicadas += 1
                                        logger.info(f"Publicada en WP: Post ID {post_id}")
                                    except Exception as e:
                                        logger.error(f"Error publicando {id_subasta}: {e}")
                                        stats.errores += 1

                            count += 1

                        except Exception as e:
                            logger.error(f"Error procesando {id_subasta}: {e}")
                            stats.errores += 1

                except Exception as e:
                    logger.error(f"Error en provincia {nombre_provincia}: {e}")
                    stats.errores += 1

                # Registrar en log de BD
                if db and not dry_run:
                    db.log_sync(
                        provincia_codigo=cod_provincia,
                        encontradas=stats.encontradas,
                        nuevas=stats.nuevas,
                        actualizadas=stats.actualizadas,
                        publicadas=stats.publicadas,
                        errores=stats.errores,
                        duracion=stats.duracion,
                    )

                results[cod_provincia] = stats
                logger.info(f"Resultado {nombre_provincia}: {stats}")

                # Acumular totales
                total_stats.encontradas += stats.encontradas
                total_stats.nuevas += stats.nuevas
                total_stats.actualizadas += stats.actualizadas
                total_stats.publicadas += stats.publicadas
                total_stats.errores += stats.errores

    finally:
        if db:
            db.close()

    # Resumen final
    logger.info("\n" + "=" * 60)
    logger.info("RESUMEN DE SINCRONIZACIÓN")
    logger.info("=" * 60)
    logger.info(f"Total: {total_stats}")
    logger.info("=" * 60)

    return results


def test_connections() -> dict:
    """
    Prueba las conexiones al BOE y WordPress.

    Returns:
        Diccionario con resultados de las pruebas
    """
    results = {
        "boe": False,
        "wordpress": False,
        "database": False,
    }

    logger.info("Probando conexiones...")

    # Probar BOE
    logger.info("Probando conexión al BOE...")
    try:
        with BOEScraper(headless=True) as scraper:
            results["boe"] = scraper.verificar_conexion()
        logger.info(f"BOE: {'OK' if results['boe'] else 'FALLO'}")
    except Exception as e:
        logger.error(f"Error probando BOE: {e}")

    # Probar WordPress
    logger.info("Probando conexión a WordPress...")
    try:
        client = WordPressClient()
        results["wordpress"] = client.test_connection()
        logger.info(f"WordPress: {'OK' if results['wordpress'] else 'FALLO'}")
    except Exception as e:
        logger.error(f"Error probando WordPress: {e}")

    # Probar base de datos
    logger.info("Probando base de datos...")
    try:
        db = Database(settings.DB_PATH)
        stats = db.get_estadisticas()
        results["database"] = True
        logger.info(f"Base de datos: OK ({stats['total_subastas']} subastas almacenadas)")
        db.close()
    except Exception as e:
        logger.error(f"Error probando BD: {e}")

    return results


def get_status() -> dict:
    """
    Obtiene el estado actual del sistema.

    Returns:
        Diccionario con información de estado
    """
    status = {
        "config": {
            "wp_url": settings.WP_URL,
            "provincias": settings.PROVINCIAS_CODIGOS,
            "headless": settings.SELENIUM_HEADLESS,
        },
        "database": {},
        "last_sync": None,
    }

    try:
        db = Database(settings.DB_PATH)
        status["database"] = db.get_estadisticas()
        db.close()
    except Exception as e:
        status["database"]["error"] = str(e)

    return status


if __name__ == "__main__":
    # Ejecutar sincronización por defecto
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            test_connections()
        elif sys.argv[1] == "status":
            status = get_status()
            print("\nEstado del sistema:")
            print(f"  WordPress: {status['config']['wp_url']}")
            print(f"  Provincias: {', '.join(status['config']['provincias'])}")
            print(f"  Subastas en BD: {status['database'].get('total_subastas', 0)}")
            print(f"  Publicadas: {status['database'].get('subastas_publicadas', 0)}")
        else:
            # Asumir código de provincia
            run_sync(provincia=sys.argv[1])
    else:
        run_sync()
