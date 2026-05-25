#!/usr/bin/env python3
"""
Backfill del sticky CTA contextual sobre los posts ya publicados en WP.

Quick Win #2 del plan SEO 2026. Inyecta un bloque autocontenido
(<style> + <aside> + <script>) al final del contenido de cada post de
subasta, leyendo metadatos (tipo, localidad, provincia) desde la BD
local para personalizar el subtexto y los parámetros del CTA.

Idempotente: si el post ya contiene `class="sticky-cta-subasta"`, lo
saltamos. Usa `--force` para re-inyectarlo igualmente (útil tras un
cambio de copy o estilo del bloque).

Uso típico:
    # Inventario en seco — no toca WP
    python scripts/backfill_sticky_cta.py --dry-run

    # Backfill real (paraleliza, idempotente)
    python scripts/backfill_sticky_cta.py --execute --workers 5

    # Re-inyectar (sobrescribe la versión anterior del sticky)
    python scripts/backfill_sticky_cta.py --execute --force --workers 5
"""
import argparse
import logging
import re
import sqlite3
import sys
import time
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings
from src.wordpress.client import WordPressClient


# Mismo patrón que dedup_wp_posts.py
ID_PATTERN = re.compile(r"\bSUB-[A-Z]{2}-\d{4}-[A-Z0-9]+\b")
STICKY_MARKER = 'class="sticky-cta-subasta"'

DB_PATH = Path(__file__).parent.parent / "data" / "subastas.db"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("backfill_sticky")


# Bloque autocontenido: CSS + HTML + JS. Sustituimos {variables} con
# `.format()` para no chocar con las llaves de CSS/JS. Para CSS y JS,
# duplicamos las llaves literales escapando con `{{` / `}}`.
STICKY_CTA_BLOCK_TEMPLATE = r"""
<!-- Sticky CTA - Informe jurídico contextual (Quick Win #2 SEO 2026 — backfill) -->
<style>
.sticky-cta-subasta {{
    position: fixed; bottom: 0; left: 0; right: 0;
    background: rgba(255, 255, 255, 0.97);
    border-top: 2px solid #1e40af;
    padding: 12px 16px; z-index: 9999;
    box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
    display: none;
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
}}
.sticky-cta-subasta.visible {{
    display: flex; align-items: center; justify-content: space-between;
    gap: 12px;
    animation: stickyCtaSlideUp 0.3s ease-out;
}}
@keyframes stickyCtaSlideUp {{
    from {{ transform: translateY(100%); opacity: 0; }}
    to   {{ transform: translateY(0); opacity: 1; }}
}}
.sticky-cta-subasta__info {{ flex: 1; min-width: 0; }}
.sticky-cta-subasta__title {{
    font-weight: 600; color: #1e40af; font-size: 0.95em;
    margin: 0 0 2px 0; line-height: 1.3;
}}
.sticky-cta-subasta__meta {{
    font-size: 0.8em; color: #6b7280; margin: 0; line-height: 1.3;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.sticky-cta-subasta__btn {{
    display: inline-block; background: #1e40af; color: white !important;
    padding: 10px 18px; border-radius: 6px; text-decoration: none;
    font-weight: 600; font-size: 0.9em; white-space: nowrap;
    transition: background 0.2s;
}}
.sticky-cta-subasta__btn:hover {{
    background: #1e3a8a; color: white !important;
}}
.sticky-cta-subasta__close {{
    background: none; border: none; color: #6b7280;
    font-size: 1.4em; cursor: pointer; padding: 0 6px;
    line-height: 1; flex-shrink: 0;
}}
.sticky-cta-subasta__close:hover {{ color: #1f2937; }}
@media (max-width: 640px) {{
    .sticky-cta-subasta {{ padding: 10px 12px; gap: 8px; }}
    .sticky-cta-subasta__title {{ font-size: 0.85em; }}
    .sticky-cta-subasta__meta {{ font-size: 0.72em; }}
    .sticky-cta-subasta__btn {{ padding: 9px 12px; font-size: 0.82em; }}
    body.has-sticky-cta-subasta {{ padding-bottom: 80px; }}
}}
</style>
<aside class="sticky-cta-subasta" id="sticky-cta-subasta" role="complementary" aria-label="Solicitar informe jurídico de esta subasta">
    <div class="sticky-cta-subasta__info">
        <p class="sticky-cta-subasta__title">📄 Informe jurídico de ESTE activo · 72,60€ · 48h</p>
        <p class="sticky-cta-subasta__meta">{id_subasta} · {tipo_bien} en {localidad}</p>
    </div>
    <a href="{contact_url}?subasta={id_q}&tipo={tipo_q}&localidad={localidad_q}&provincia={provincia_q}&utm_source=ficha_sticky#analisis"
       class="sticky-cta-subasta__btn"
       title="Solicitar informe jurídico de {tipo_bien} en {localidad}">
        Solicitar informe &rarr;
    </a>
    <button type="button" class="sticky-cta-subasta__close" aria-label="Cerrar" data-sticky-cta-close>&times;</button>
</aside>
<script>
(function () {{
    var STORAGE_KEY = 'sticky_cta_subasta_dismissed_at';
    var DISMISS_MS = 60 * 60 * 1000;
    var SCROLL_TRIGGER_PCT = 0.30;
    function onReady(fn) {{
        if (document.readyState !== 'loading') {{ fn(); return; }}
        document.addEventListener('DOMContentLoaded', fn);
    }}
    onReady(function () {{
        var el = document.getElementById('sticky-cta-subasta');
        if (!el) return;
        try {{
            var dismissedAt = parseInt(localStorage.getItem(STORAGE_KEY) || '0', 10);
            if (dismissedAt && (Date.now() - dismissedAt < DISMISS_MS)) return;
        }} catch (e) {{ }}
        var shown = false;
        function maybeShow() {{
            if (shown) return;
            var scrolled = window.scrollY || window.pageYOffset || 0;
            var docHeight = Math.max(
                document.body.scrollHeight,
                document.documentElement.scrollHeight
            ) - window.innerHeight;
            if (docHeight <= 0) return;
            if (scrolled / docHeight >= SCROLL_TRIGGER_PCT) {{
                el.classList.add('visible');
                document.body.classList.add('has-sticky-cta-subasta');
                shown = true;
                window.removeEventListener('scroll', maybeShow);
            }}
        }}
        window.addEventListener('scroll', maybeShow, {{ passive: true }});
        maybeShow();
        var closeBtn = el.querySelector('[data-sticky-cta-close]');
        if (closeBtn) {{
            closeBtn.addEventListener('click', function () {{
                el.classList.remove('visible');
                document.body.classList.remove('has-sticky-cta-subasta');
                try {{ localStorage.setItem(STORAGE_KEY, String(Date.now())); }} catch (e) {{ }}
            }});
        }}
    }});
}})();
</script>
"""


def extract_id_subasta(html: str) -> Optional[str]:
    """Extrae el id_subasta del HTML del post (mismo criterio que dedup)."""
    if not html:
        return None
    matches = ID_PATTERN.findall(html)
    if not matches:
        return None
    return Counter(matches).most_common(1)[0][0]


def load_subasta_meta(conn: sqlite3.Connection, id_subasta: str) -> Optional[dict]:
    """Lee tipo/localidad/provincia del bien principal desde la BD local."""
    row = conn.execute(
        """
        SELECT b.subtipo_bien, b.tipo_bien, b.localidad, b.provincia
          FROM bienes b
         WHERE b.id_subasta = ?
         ORDER BY b.numero_bien ASC
         LIMIT 1
        """,
        (id_subasta,),
    ).fetchone()
    if not row:
        return None
    return {
        "tipo_bien": row[0] or row[1] or "Inmueble",
        "localidad": row[2] or "España",
        "provincia": row[3] or "España",
    }


def build_sticky_block(
    id_subasta: str,
    tipo_bien: str,
    localidad: str,
    provincia: str,
    contact_url: str,
) -> str:
    return STICKY_CTA_BLOCK_TEMPLATE.format(
        id_subasta=id_subasta,
        tipo_bien=tipo_bien,
        localidad=localidad,
        contact_url=contact_url,
        id_q=urllib.parse.quote(id_subasta),
        tipo_q=urllib.parse.quote(tipo_bien),
        localidad_q=urllib.parse.quote(localidad),
        provincia_q=urllib.parse.quote(provincia),
    )


def list_all_posts(client: WordPressClient, page_size: int = 100, sleep: float = 0.3):
    """Itera todos los posts publicados, paginando."""
    page = 1
    seen_ids = set()
    total = 0
    while True:
        try:
            response = requests.get(
                f"{client.api_url}/posts",
                headers=client.headers,
                params={
                    "per_page": page_size,
                    "page": page,
                    "status": "publish",
                    "_fields": "id,slug,link,content,status",
                    "orderby": "id",
                    "order": "asc",
                },
                timeout=60,
            )
        except requests.RequestException as e:
            logger.error(f"Error en página {page}: {e}; reintentando en 5s")
            time.sleep(5)
            continue

        if response.status_code == 400:
            break
        if response.status_code != 200:
            logger.error(f"HTTP {response.status_code} en página {page}: {response.text[:200]}")
            break

        posts = response.json()
        if not posts:
            break

        new_posts = [p for p in posts if p["id"] not in seen_ids]
        for p in new_posts:
            seen_ids.add(p["id"])
        total += len(new_posts)
        for p in new_posts:
            yield p

        if len(posts) < page_size:
            break
        page += 1
        if page % 10 == 0:
            logger.info(f"  ... página {page}, {total} posts vistos")
        time.sleep(sleep)


def remove_existing_sticky(html: str) -> str:
    """Borra el bloque sticky previo (HTML + marcador) para re-inyección."""
    # Pareja comentario de cabecera ↔ </script> final del bloque que escribimos
    pattern = re.compile(
        r"<!-- Sticky CTA - Informe jurídico contextual.*?</script>\s*",
        re.DOTALL,
    )
    return pattern.sub("", html)


def process_post(
    client: WordPressClient,
    conn: sqlite3.Connection,
    post: dict,
    contact_url: str,
    force: bool,
    dry_run: bool,
) -> str:
    """Procesa un post. Devuelve un código resultado para el resumen."""
    post_id = post["id"]
    content = post.get("content", {}) or {}
    rendered = content.get("rendered", "") if isinstance(content, dict) else ""

    if not rendered:
        return "skipped_empty"

    already_present = STICKY_MARKER in rendered
    if already_present and not force:
        return "skipped_already"

    id_subasta = extract_id_subasta(rendered)
    if not id_subasta:
        return "skipped_no_id"

    meta = load_subasta_meta(conn, id_subasta)
    if not meta:
        return "skipped_no_db"

    block = build_sticky_block(
        id_subasta=id_subasta,
        tipo_bien=meta["tipo_bien"],
        localidad=meta["localidad"],
        provincia=meta["provincia"],
        contact_url=contact_url,
    )

    new_content = remove_existing_sticky(rendered) if already_present else rendered
    new_content = new_content.rstrip() + "\n" + block

    if dry_run:
        return "would_update_present" if already_present else "would_update_new"

    try:
        response = requests.put(
            f"{client.api_url}/posts/{post_id}",
            headers=client.headers,
            json={"content": new_content},
            timeout=45,
        )
        if response.status_code == 200:
            return "updated_present" if already_present else "updated_new"
        logger.error(f"HTTP {response.status_code} actualizando post {post_id}: {response.text[:200]}")
        return "error"
    except requests.RequestException as e:
        logger.error(f"Error actualizando post {post_id}: {e}")
        return "error"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Aplica cambios (default es dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="No tocar WP, solo reportar")
    parser.add_argument("--force", action="store_true", help="Re-inyectar el bloque aunque ya esté presente")
    parser.add_argument("--limit", type=int, default=0, help="Procesar como mucho N posts (0 = todos)")
    parser.add_argument("--workers", type=int, default=3, help="Paralelismo (cuidado con rate limits WP)")
    parser.add_argument("--sleep", type=float, default=0.3, help="Pausa entre páginas al listar posts")
    args = parser.parse_args()

    dry_run = not args.execute or args.dry_run
    mode = "DRY-RUN" if dry_run else "EXECUTE"
    logger.info(f"Modo: {mode} | force={args.force} | workers={args.workers} | limit={args.limit or '∞'}")

    if not DB_PATH.exists():
        logger.error(f"BD no encontrada: {DB_PATH}")
        sys.exit(1)

    client = WordPressClient()
    if not client.test_connection():
        logger.error("No se pudo conectar a WordPress")
        sys.exit(1)

    contact_url = settings.WP_CONTACT_FORM_URL

    # Conexión SQLite por hilo (sqlite3 no es thread-safe por defecto)
    def make_conn():
        return sqlite3.connect(DB_PATH, check_same_thread=False)

    # Cargar posts a memoria primero (paginar puede ser lento con WP)
    logger.info("Listando posts publicados…")
    posts = []
    for p in list_all_posts(client, sleep=args.sleep):
        posts.append(p)
        if args.limit and len(posts) >= args.limit:
            logger.info(f"Alcanzado --limit {args.limit}")
            break
    logger.info(f"Total posts a evaluar: {len(posts)}")

    counts: Counter = Counter()
    start = time.time()

    # Una conexión por hilo del pool
    thread_local_conns = {}

    def worker(post):
        import threading
        tid = threading.get_ident()
        conn = thread_local_conns.get(tid)
        if conn is None:
            conn = make_conn()
            thread_local_conns[tid] = conn
        return process_post(client, conn, post, contact_url, args.force, dry_run)

    if args.workers <= 1:
        conn = make_conn()
        for post in posts:
            counts[process_post(client, conn, post, contact_url, args.force, dry_run)] += 1
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(worker, p) for p in posts]
            for i, fut in enumerate(as_completed(futures), 1):
                counts[fut.result()] += 1
                if i % 50 == 0:
                    logger.info(f"  procesados {i}/{len(posts)}")

    for conn in thread_local_conns.values():
        conn.close()

    duracion = time.time() - start
    print("\n=== RESUMEN BACKFILL STICKY CTA ===")
    print(f"  modo: {mode}")
    print(f"  posts evaluados: {len(posts)}")
    print(f"  duración: {duracion:.0f}s")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")

    if dry_run:
        print("\n(dry-run) ningún post modificado. Usa --execute para aplicar.")


if __name__ == "__main__":
    main()
