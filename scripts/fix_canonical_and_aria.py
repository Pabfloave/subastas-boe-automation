#!/usr/bin/env python3
"""
Backfill SEO: regenera HTML y meta de los posts publicados aplicando los
3 fixes recientes:

  1. Canonical URL Rank Math: pasa de "" (vacío) al permalink real del
     post — evita canibalización por canonicals incorrectos.
  2. Constantes de marca/URL: hace efectivos los reemplazos de literales
     (`https://comprarensubasta.com`, `CAFAVE INVESTMENT`, ...).
  3. aria-hidden en emojis: envuelve los emojis de headings/links en
     <span aria-hidden="true"> para que screen readers los salten.

Solo toca `content` y `meta` de cada post (no cambia título, categorías ni
slug, así que las URLs indexadas se preservan). Idempotente.

Uso:
    # Dry-run (default): muestra cuántos se actualizarían
    python scripts/fix_canonical_and_aria.py

    # Aplicar a todos
    python scripts/fix_canonical_and_aria.py --execute

    # Aplicar a una muestra de 5 (validación)
    python scripts/fix_canonical_and_aria.py --execute --limit 5

    # Limitar concurrencia (default 5)
    python scripts/fix_canonical_and_aria.py --execute --workers 8
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
from src.wordpress.client import WordPressClient
from src.wordpress.publisher import WordPressPublisher


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill-seo")


def regenerate_post(publisher: WordPressPublisher, client: WordPressClient,
                    subasta, wp_post_id: int) -> tuple[int, int]:
    """
    Regenera content + meta para un post ya existente.

    Devuelve (wp_post_id, status_code). status_code=0 indica excepción
    de red o WP responde sin código (p. ej. post borrado en WP).
    """
    try:
        # Obtenemos el post para tomar el permalink real (canonical).
        # WP devuelve `link` con la URL pública del post, que es lo que
        # queremos como canonical.
        post = client.get_post(wp_post_id)
        if not post:
            logger.warning(f"Post {wp_post_id} no existe en WP (subasta {subasta.id_subasta})")
            return wp_post_id, 404
        canonical_url = post.get("link", "")

        # Regenerar HTML y meta con el publisher (ya incluye los fixes)
        content = publisher._generate_content(subasta)
        meta = publisher._generate_meta(subasta, canonical_url=canonical_url)

        client.update_post(wp_post_id, {"content": content, "meta": meta})
        return wp_post_id, 200
    except Exception as e:
        logger.error(f"Error regenerando post {wp_post_id}: {e}")
        return wp_post_id, 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--execute", action="store_true",
                        help="Aplicar cambios. Sin este flag se hace dry-run.")
    parser.add_argument("--workers", type=int, default=5,
                        help="Hilos paralelos (default 5)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Procesar solo N posts (0 = todos)")
    parser.add_argument("--yes", action="store_true",
                        help="Saltar confirmación interactiva")
    args = parser.parse_args()

    db = Database(settings.DB_PATH)
    todas = db.get_subastas_publicadas()
    db.close()

    con_post = [s for s in todas if s.wp_post_id and s.activa]
    if args.limit:
        con_post = con_post[: args.limit]

    logger.info(f"Subastas publicadas activas: {len(con_post)}")

    if not con_post:
        return

    if not args.execute:
        print("\n[DRY-RUN] No se modifica nada. Usa --execute para aplicar.")
        print(f"Se regenerarían {len(con_post)} posts (content + meta).")
        print("\nMuestra de las primeras 5:")
        for s in con_post[:5]:
            print(f"  {s.id_subasta} | wp_post_id={s.wp_post_id}")
        return

    if not args.yes:
        confirm = input(f"\n¿Regenerar {len(con_post)} posts? [escribe 'SI']: ")
        if confirm != "SI":
            print("Cancelado.")
            return

    client = WordPressClient()
    publisher = WordPressPublisher(client=client)

    ok = []
    fail = []
    start = time.time()
    total = len(con_post)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_subasta = {
            executor.submit(regenerate_post, publisher, client, s, s.wp_post_id): s
            for s in con_post
        }
        for i, future in enumerate(as_completed(future_to_subasta), 1):
            s = future_to_subasta[future]
            post_id, status = future.result()
            if status == 200:
                ok.append(s.id_subasta)
            else:
                fail.append((s.id_subasta, post_id, status))
            if i % 25 == 0 or i == total:
                rate = i / (time.time() - start)
                eta = (total - i) / rate if rate > 0 else 0
                logger.info(f"  {i}/{total} ({rate:.1f}/s, ETA {eta/60:.1f}min)")

    duracion = time.time() - start
    logger.info(f"Completado: {len(ok)} OK, {len(fail)} fallos en {duracion/60:.1f}min")

    if fail:
        print(f"\nPrimeros 10 fallos:")
        for id_sub, post_id, status in fail[:10]:
            print(f"  {id_sub} (post {post_id}): HTTP {status}")


if __name__ == "__main__":
    main()
