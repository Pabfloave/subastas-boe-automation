#!/usr/bin/env python3
"""
Inventario y deduplicación de posts en WordPress.

Detecta posts que comparten el mismo `id_subasta` (extraído del contenido
HTML del post), mantiene el más reciente y mueve el resto a la papelera
(o los borra permanentemente con --force-delete).

Uso típico:
    # 1) Inventariar (escribe scripts/wp_inventory.json, no toca WP)
    python scripts/dedup_wp_posts.py inventory

    # 2) Revisar el JSON, después dedup en seco
    python scripts/dedup_wp_posts.py dedup --dry-run

    # 3) Ejecutar dedup real (borrado permanente, paraleliza)
    python scripts/dedup_wp_posts.py dedup --execute --workers 5

    # 4) Reconstruir mapeo wp_post_id en la BD local
    python scripts/dedup_wp_posts.py rebuild-db
"""
import argparse
import json
import logging
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings
from src.wordpress.client import WordPressClient


INVENTORY_PATH = Path(__file__).parent / "wp_inventory.json"

# Coincide con identificadores como SUB-JA-2026-260596, SUB-RC-2026-3800100126013,
# SUB-AT-2025-25R4186001631, SUB-JV-2026-260620, etc.
ID_PATTERN = re.compile(r"\bSUB-[A-Z]{2}-\d{4}-[A-Z0-9]+\b")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("dedup")


def extract_id_subasta(html: str) -> Optional[str]:
    """Extrae el id_subasta del HTML de un post.

    El id aparece varias veces (tabla "Identificador", URL del BOE, schema
    JSON-LD, CTA). Devolvemos el más frecuente para tolerar coincidencias
    espurias.
    """
    if not html:
        return None
    matches = ID_PATTERN.findall(html)
    if not matches:
        return None
    return Counter(matches).most_common(1)[0][0]


def list_all_posts(client: WordPressClient, page_size: int = 100, sleep: float = 0.3):
    """Itera todos los posts publicados y borradores, paginando."""
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
                    "status": "any",
                    "_fields": "id,slug,date,modified,content,link,status",
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
            # WP devuelve 400 cuando page > total_pages
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
        if page % 20 == 0:
            logger.info(f"  ... página {page}, {total} posts vistos")
        time.sleep(sleep)


def cmd_inventory(args):
    """Recorre todos los posts y agrupa por id_subasta. Escribe JSON."""
    client = WordPressClient()

    # Total esperado
    head = requests.get(
        f"{client.api_url}/posts",
        headers=client.headers,
        params={"per_page": 1, "status": "any"},
        timeout=30,
    )
    total_wp = int(head.headers.get("X-WP-Total", "0"))
    logger.info(f"WP reporta {total_wp} posts en total")

    posts_by_id = defaultdict(list)
    posts_no_id = []
    counter = 0
    start = time.time()

    for post in list_all_posts(client, page_size=100, sleep=args.sleep):
        counter += 1
        content = post.get("content", {})
        rendered = content.get("rendered", "") if isinstance(content, dict) else ""
        id_subasta = extract_id_subasta(rendered)

        entry = {
            "id": post["id"],
            "slug": post.get("slug", ""),
            "date": post.get("date", ""),
            "modified": post.get("modified", ""),
            "link": post.get("link", ""),
            "status": post.get("status", ""),
        }
        if id_subasta:
            posts_by_id[id_subasta].append(entry)
        else:
            posts_no_id.append(entry)

        if args.limit and counter >= args.limit:
            logger.info(f"Alcanzado --limit {args.limit}, parando")
            break

    duracion = time.time() - start
    logger.info(f"Inventario completo: {counter} posts en {duracion:.0f}s")

    duplicates = {k: v for k, v in posts_by_id.items() if len(v) > 1}
    to_delete_count = sum(len(v) - 1 for v in duplicates.values())

    summary = {
        "scanned_at": datetime.now().isoformat(),
        "total_posts": counter,
        "wp_reported_total": total_wp,
        "unique_subastas": len(posts_by_id),
        "posts_sin_id": len(posts_no_id),
        "subastas_con_duplicados": len(duplicates),
        "posts_a_borrar_si_dedup": to_delete_count,
    }

    inventory = {
        "summary": summary,
        "by_id": dict(posts_by_id),
        "no_id": posts_no_id,
    }
    INVENTORY_PATH.write_text(json.dumps(inventory, indent=2, ensure_ascii=False))
    logger.info(f"Inventario guardado en {INVENTORY_PATH}")

    print("\n=== RESUMEN INVENTARIO ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    if duplicates:
        print("\nTop 10 subastas con más duplicados:")
        top = sorted(duplicates.items(), key=lambda x: -len(x[1]))[:10]
        for id_sub, posts in top:
            print(f"  {id_sub}: {len(posts)} posts (oldest: {min(p['date'] for p in posts)})")


def _delete_post(client: WordPressClient, post_id: int, force: bool, max_retries: int = 3) -> tuple[int, int]:
    """Borra un post con reintentos exponenciales. Devuelve (post_id, status_code)."""
    params = {"force": "true"} if force else {}
    last_status = 0
    for attempt in range(max_retries):
        try:
            response = requests.delete(
                f"{client.api_url}/posts/{post_id}",
                headers=client.headers,
                params=params,
                timeout=30,
            )
            last_status = response.status_code
            # 200 OK, 410 Gone (ya estaba borrado) → éxito
            if last_status in (200, 410, 404):
                return post_id, last_status
            # 5xx o 429 → reintentable
            if last_status >= 500 or last_status == 429:
                time.sleep(2 ** attempt)
                continue
            # 4xx no reintentable
            return post_id, last_status
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
    return post_id, last_status


def cmd_dedup(args):
    """Lee inventario y borra duplicados (mantiene el más reciente)."""
    if not INVENTORY_PATH.exists():
        logger.error(f"Falta inventario: {INVENTORY_PATH}. Ejecuta inventory primero.")
        sys.exit(1)

    inventory = json.loads(INVENTORY_PATH.read_text())
    by_id = inventory["by_id"]

    # Filtrar solo subastas con duplicados
    duplicates = {k: v for k, v in by_id.items() if len(v) > 1}
    posts_a_borrar = []
    survivors = {}

    for id_sub, posts in duplicates.items():
        # Mantener el de mayor fecha de modificación; si empatan, el de mayor ID
        posts_sorted = sorted(
            posts,
            key=lambda p: (p.get("modified", ""), p["id"]),
            reverse=True,
        )
        survivor = posts_sorted[0]
        survivors[id_sub] = survivor["id"]
        for p in posts_sorted[1:]:
            posts_a_borrar.append(p["id"])

    logger.info(f"Subastas con duplicados: {len(duplicates)}")
    logger.info(f"Posts a borrar: {len(posts_a_borrar)}")
    logger.info(f"Posts sobrevivientes: {len(survivors)}")

    if args.dry_run:
        print("\n[DRY-RUN] No se borrará nada. Ejemplos:")
        for id_sub, posts in list(duplicates.items())[:5]:
            sobreviv = survivors[id_sub]
            print(f"  {id_sub}: mantener post {sobreviv}, borrar {[p['id'] for p in posts if p['id'] != sobreviv]}")
        return

    # Confirmar antes de borrar masivamente
    if not args.yes:
        resp = input(f"\n¿Borrar {len(posts_a_borrar)} posts? [escribe 'BORRAR']: ")
        if resp != "BORRAR":
            print("Cancelado.")
            return

    client = WordPressClient()
    deleted_ok = 0
    deleted_fail = []
    start = time.time()

    # Ejecutar en paralelo con thread pool
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(_delete_post, client, pid, args.force_delete): pid
            for pid in posts_a_borrar
        }
        for i, future in enumerate(as_completed(futures), 1):
            post_id, status = future.result()
            if status in (200, 410):
                deleted_ok += 1
            else:
                deleted_fail.append((post_id, status))
            if i % 100 == 0:
                rate = i / (time.time() - start)
                eta = (len(posts_a_borrar) - i) / rate if rate > 0 else 0
                logger.info(f"  {i}/{len(posts_a_borrar)} ({rate:.1f} req/s, ETA {eta/60:.0f}min)")

    duracion = time.time() - start
    logger.info(f"Borrado completo en {duracion/60:.1f}min: {deleted_ok} OK, {len(deleted_fail)} errores")

    # Guardar resumen de la operación
    result_path = Path(__file__).parent / "dedup_result.json"
    result_path.write_text(json.dumps({
        "executed_at": datetime.now().isoformat(),
        "duracion_segundos": duracion,
        "deleted_ok": deleted_ok,
        "deleted_fail": deleted_fail,
        "survivors": survivors,
    }, indent=2))
    logger.info(f"Resultado guardado en {result_path}")


def cmd_rebuild_db(args):
    """Actualiza la BD local: wp_post_id apunta al post sobreviviente."""
    if not INVENTORY_PATH.exists():
        logger.error(f"Falta inventario: {INVENTORY_PATH}. Ejecuta inventory primero.")
        sys.exit(1)

    inventory = json.loads(INVENTORY_PATH.read_text())
    by_id = inventory["by_id"]

    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row

    # Mapeo id_subasta -> wp_post_id (sobreviviente)
    survivors = {}
    for id_sub, posts in by_id.items():
        # Si ya hubo dedup, solo queda 1; si no, escogemos el más reciente
        posts_sorted = sorted(
            posts,
            key=lambda p: (p.get("modified", ""), p["id"]),
            reverse=True,
        )
        survivors[id_sub] = posts_sorted[0]["id"]

    cursor = conn.cursor()
    cursor.execute("SELECT id_subasta, wp_post_id, publicado_wp FROM subastas")
    rows = cursor.fetchall()

    updated = 0
    cleared = 0
    matched = 0
    not_in_wp = 0

    for row in rows:
        id_sub = row["id_subasta"]
        current = row["wp_post_id"]
        wp_id = survivors.get(id_sub)

        if wp_id is None:
            # Subasta no aparece en WP (posiblemente borrada)
            not_in_wp += 1
            if not args.dry_run and current is not None:
                cursor.execute(
                    "UPDATE subastas SET wp_post_id = NULL, publicado_wp = 0 WHERE id_subasta = ?",
                    (id_sub,),
                )
                cleared += 1
            continue

        if current == wp_id:
            matched += 1
        else:
            if not args.dry_run:
                cursor.execute(
                    "UPDATE subastas SET wp_post_id = ?, publicado_wp = 1 WHERE id_subasta = ?",
                    (wp_id, id_sub),
                )
            updated += 1

    if not args.dry_run:
        conn.commit()
    conn.close()

    print("\n=== RESUMEN REBUILD-DB ===")
    print(f"  Subastas en BD que coinciden con WP: {matched}")
    print(f"  Subastas con wp_post_id actualizado: {updated}")
    print(f"  Subastas no encontradas en WP: {not_in_wp}")
    print(f"  Posts borrados/desvinculados: {cleared}")
    print(f"  Subastas en WP sin entrada en BD: {len(survivors) - matched - updated}")
    if args.dry_run:
        print("\n[DRY-RUN] Sin cambios. Ejecuta sin --dry-run para aplicar.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_inv = sub.add_parser("inventory", help="Inventariar posts WP por id_subasta")
    p_inv.add_argument("--limit", type=int, default=0, help="Limitar nº de posts (debug)")
    p_inv.add_argument("--sleep", type=float, default=0.3, help="Sleep entre páginas (s)")

    p_dedup = sub.add_parser("dedup", help="Borrar duplicados según inventario")
    p_dedup.add_argument("--dry-run", action="store_true", default=True)
    p_dedup.add_argument("--execute", action="store_true", help="Desactiva dry-run")
    p_dedup.add_argument("--workers", type=int, default=4, help="Hilos paralelos para DELETE")
    p_dedup.add_argument("--force-delete", action="store_true", default=True,
                         help="DELETE permanente con force=true (default)")
    p_dedup.add_argument("--trash", action="store_true",
                         help="Mover a papelera en vez de borrar permanente")
    p_dedup.add_argument("--yes", action="store_true", help="Sin confirmación interactiva")

    p_rebuild = sub.add_parser("rebuild-db", help="Reconstruir wp_post_id en la BD local")
    p_rebuild.add_argument("--dry-run", action="store_true", default=False)

    args = parser.parse_args()

    if args.cmd == "inventory":
        cmd_inventory(args)
    elif args.cmd == "dedup":
        if args.execute:
            args.dry_run = False
        if args.trash:
            args.force_delete = False
        cmd_dedup(args)
    elif args.cmd == "rebuild-db":
        cmd_rebuild_db(args)


if __name__ == "__main__":
    main()
