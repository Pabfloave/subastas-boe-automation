#!/usr/bin/env python3
"""
Backfill: regenera el bloque de mapa (iframe) en todos los posts WP publicados
usando el nuevo geocoder con cache.

Lee subastas con `publicado_wp=1 AND wp_post_id IS NOT NULL` y, para cada una,
regenera el HTML del post (que ahora pasa por el geocoder) y hace PUT a WP.

El cache de geocoding persiste en `data/subastas.db` → tabla `geocode_cache`,
de modo que repeticiones (re-ejecutar el script, o publicar la misma subasta
de nuevo) no incurren coste.

Uso:
    # Dry-run sobre los 20 primeros (no toca WP ni Google, solo muestra qué pasaría)
    python scripts/regeocode_posts.py --limit 20

    # Test real sobre 20 subastas (llama a Google, cachea, actualiza WP)
    python scripts/regeocode_posts.py --limit 20 --execute

    # Backfill completo
    python scripts/regeocode_posts.py --execute

    # Solo geocodificar (poblar cache) sin tocar WP
    python scripts/regeocode_posts.py --execute --geocode-only

Coste estimado: ~$0.005 por nueva dirección (Google Geocoding API).
Hay $200/mes gratis = ~40.000 lookups gratis.
"""
import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings
from src.models.database import Database
from src.services.geocoder import Geocoder
from src.wordpress.client import WordPressClient
from src.wordpress.publisher import WordPressPublisher


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("regeocode")


def regenerar_post(
    publisher: WordPressPublisher,
    subasta,
    execute: bool,
    geocode_only: bool,
) -> tuple[str, str, int]:
    """
    Regenera contenido de un post.

    Returns:
        (id_subasta, estado, http_status)
        estado: 'ok' | 'sin_post' | 'sin_bienes' | 'wp_error' | 'dry_run' | 'geocoded'
    """
    if not subasta.wp_post_id:
        return subasta.id_subasta, "sin_post", 0

    bienes_con_direccion = [
        b for b in (subasta.bienes or [])
        if (b.direccion and b.localidad)
    ]
    if not bienes_con_direccion:
        return subasta.id_subasta, "sin_bienes", 0

    # Si solo queremos poblar el cache de geocoding sin tocar WP:
    if geocode_only:
        for bien in bienes_con_direccion:
            publisher.geocoder.geocode(
                direccion=bien.direccion,
                localidad=bien.localidad,
                provincia=bien.provincia,
                codigo_postal=bien.codigo_postal,
            )
        return subasta.id_subasta, "geocoded", 0

    # Regenerar contenido (esto llama internamente al geocoder)
    content = publisher._generate_content(subasta)

    if not execute:
        return subasta.id_subasta, "dry_run", 0

    try:
        publisher.client.update_post(subasta.wp_post_id, {"content": content})
        return subasta.id_subasta, "ok", 200
    except Exception as e:
        logger.warning("WP error en %s (post %s): %s", subasta.id_subasta, subasta.wp_post_id, e)
        return subasta.id_subasta, "wp_error", 0


def cache_stats(db_path: str) -> dict:
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        ok = conn.execute("SELECT COUNT(*) FROM geocode_cache WHERE status='ok'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM geocode_cache WHERE status='failed'").fetchone()[0]
        return {"ok": ok, "failed": failed, "total": ok + failed}
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--execute", action="store_true",
                        help="Aplicar cambios. Sin esto es dry-run.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Máximo nº de subastas a procesar (0 = todas)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Hilos paralelos para PUTs a WP (default 4)")
    parser.add_argument("--geocode-only", action="store_true",
                        help="Solo poblar cache de geocoding, no actualizar WP")
    parser.add_argument("--yes", action="store_true",
                        help="Sin confirmación interactiva")
    args = parser.parse_args()

    if not settings.GOOGLE_MAPS_API_KEY:
        logger.error("GOOGLE_MAPS_API_KEY no configurada en .env — abortando")
        sys.exit(1)

    db = Database(settings.DB_PATH)
    subastas = db.get_subastas_publicadas()
    db.close()

    if args.limit:
        subastas = subastas[: args.limit]

    total = len(subastas)
    logger.info("Subastas publicadas a procesar: %d", total)
    logger.info("Cache antes: %s", cache_stats(settings.DB_PATH))

    if total == 0:
        return

    if not args.execute:
        print("\n[DRY-RUN] No se toca WP ni se llama a Google. Usa --execute.")
        print("Primeras 5 subastas que se procesarían:")
        for s in subastas[:5]:
            print(f"  {s.id_subasta} (post {s.wp_post_id}) — {len(s.bienes or [])} bienes")
        return

    if not args.yes:
        accion = "GEOCODIFICAR (sin tocar WP)" if args.geocode_only else "REGENERAR POSTS"
        confirm = input(f"\n¿Confirmar {accion} sobre {total} subastas? [escribe 'SI']: ")
        if confirm != "SI":
            print("Cancelado.")
            return

    client = WordPressClient()
    publisher = WordPressPublisher(client=client, geocoder=Geocoder())

    contadores = {"ok": 0, "sin_post": 0, "sin_bienes": 0, "wp_error": 0, "dry_run": 0, "geocoded": 0}
    start = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(regenerar_post, publisher, s, args.execute, args.geocode_only): s.id_subasta
            for s in subastas
        }
        for i, future in enumerate(as_completed(futures), 1):
            id_subasta, estado, http = future.result()
            contadores[estado] = contadores.get(estado, 0) + 1
            if i % 25 == 0:
                rate = i / (time.time() - start)
                eta_min = (total - i) / rate / 60 if rate > 0 else 0
                logger.info("  %d/%d (%.1f/s, ETA %.1f min) — %s", i, total, rate, eta_min, contadores)

    duracion = time.time() - start
    logger.info("Hecho en %.1f min", duracion / 60)
    logger.info("Resultado: %s", contadores)
    logger.info("Cache después: %s", cache_stats(settings.DB_PATH))


if __name__ == "__main__":
    main()
