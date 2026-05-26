#!/usr/bin/env python3
"""
Arregla los links del CTA "Solicitar Análisis Gratuito" en posts ya publicados.

Antes del fix en publisher.py, los links se generaban así:
    https://comprarensubasta.com/#analisis?subasta=X&tipo=Y&...
Pero el `#analisis` viene antes del `?`, así que todo el query string queda
DENTRO del fragment (hash) y no se manda al servidor. Resultado: la captura
de subasta del HTTP_REFERER (que el plugin WordPress usa para rellenar la
tabla `wp_subastas_inversores` y los Smart Tags `{subasta_id}` etc.) NUNCA
funcionó.

Este script itera todos los posts via REST API, encuentra los hrefs rotos
y los reescribe a la forma correcta:
    https://comprarensubasta.com/?subasta=X&tipo=Y&...#analisis

Uso:
    # Dry-run: cuenta posts afectados sin tocar nada (defecto)
    python scripts/fix_cta_links.py

    # Ejecutar el fix
    python scripts/fix_cta_links.py --execute

    # Limitar a N posts (útil para probar con un subconjunto)
    python scripts/fix_cta_links.py --execute --limit 10
"""
import argparse
import logging
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.wordpress.client import WordPressClient


# href roto: https://comprarensubasta.com/#analisis?subasta=...&provincia=...
# captura el query string entero (todo lo que va entre `?` y el cierre de
# atributo `"` o `'`, o un espacio). El `&` en HTML guardado puede aparecer
# tanto como `&` como `&amp;`, así que el patrón acepta ambos.
BROKEN_HREF = re.compile(
    r'https://comprarensubasta\.com/#analisis\?([^"\'\s<>]+)',
    re.IGNORECASE,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("fix_cta_links")


def fix_broken_links(html: str) -> tuple[str, int]:
    """Devuelve (html_fijo, número_de_reemplazos)."""
    count = 0

    def _replace(m):
        nonlocal count
        count += 1
        query = m.group(1)
        return f"https://comprarensubasta.com/?{query}#analisis"

    fixed = BROKEN_HREF.sub(_replace, html)
    return fixed, count


def iter_all_posts(client: WordPressClient, per_page: int = 100):
    """Itera todos los posts publicados via REST API, contexto edit (devuelve content.raw)."""
    page = 1
    while True:
        url = f"{client.api_url}/posts"
        params = {
            "per_page": per_page,
            "page": page,
            "status": "publish",
            "context": "edit",  # requiere auth, devuelve content.raw
            "_fields": "id,title,content,link",
        }
        r = requests.get(url, headers=client.headers, params=params, timeout=60)
        if r.status_code == 400:
            # Excedimos el último page → fin
            return
        r.raise_for_status()
        batch = r.json()
        if not batch:
            return
        for post in batch:
            yield post
        if len(batch) < per_page:
            return
        page += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Aplica los cambios. Sin esto sólo cuenta.")
    parser.add_argument("--limit", type=int, default=0, help="Limita el número de posts a procesar.")
    parser.add_argument("--sleep", type=float, default=0.1, help="Pausa entre updates (segundos) para no saturar la API.")
    args = parser.parse_args()

    client = WordPressClient()
    if not client.test_connection():
        logger.error("No se pudo conectar a WordPress. Revisa WP_URL / WP_USER / WP_APP_PASSWORD.")
        sys.exit(1)

    affected = []
    scanned = 0

    for post in iter_all_posts(client):
        scanned += 1
        # context=edit devuelve content.raw; si por alguna razón no, fallback a rendered
        content_obj = post.get("content") or {}
        html = content_obj.get("raw") or content_obj.get("rendered") or ""
        fixed, n = fix_broken_links(html)
        if n > 0:
            affected.append((post["id"], post.get("title", {}).get("rendered", ""), n, fixed))
            logger.info(f"  ↳ post {post['id']} ({n} reemplazos): {post.get('link', '')}")
        if args.limit and len(affected) >= args.limit:
            break

    logger.info("─" * 60)
    logger.info(f"Posts escaneados: {scanned}")
    logger.info(f"Posts afectados:  {len(affected)}")
    total_replacements = sum(n for _, _, n, _ in affected)
    logger.info(f"Reemplazos totales: {total_replacements}")

    if not args.execute:
        logger.info("Dry-run. Lanza con --execute para aplicar los cambios.")
        return

    if not affected:
        logger.info("Nada que hacer.")
        return

    logger.info("Aplicando updates…")
    ok, fail = 0, 0
    for post_id, title, n, fixed_html in affected:
        try:
            client.update_post(post_id, {"content": fixed_html})
            ok += 1
            logger.info(f"  ✓ post {post_id} actualizado ({n} reemplazos)")
        except Exception as e:
            fail += 1
            logger.error(f"  ✗ post {post_id} ERROR: {e}")
        time.sleep(args.sleep)

    logger.info(f"Resumen: {ok} OK, {fail} fallos.")


if __name__ == "__main__":
    main()
