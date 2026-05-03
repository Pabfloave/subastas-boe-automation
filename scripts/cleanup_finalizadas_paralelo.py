#!/usr/bin/env python3
"""
Despublicado paralelo de subastas finalizadas (cleanup express).

Toma todas las subastas con `activa=1` y `fecha_conclusion` ya pasada,
y las despublica en WordPress (status=draft) más, opcionalmente, las
borra permanentemente. Marca también la BD local como inactiva.

A diferencia de `cli.py cleanup`, este script NO verifica el BOE
(asume que si la fecha pasó, la subasta terminó), y paraleliza las
peticiones a WP. Pensado para una limpieza masiva inicial.

Uso:
    # Dry-run (default)
    python scripts/cleanup_finalizadas_paralelo.py

    # Ejecutar (mover a borrador)
    python scripts/cleanup_finalizadas_paralelo.py --execute

    # Ejecutar y borrar permanentemente
    python scripts/cleanup_finalizadas_paralelo.py --execute --delete

    # Solo subastas vencidas hace más de N días
    python scripts/cleanup_finalizadas_paralelo.py --execute --min-days 7
"""
import argparse
import logging
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings
from src.wordpress.client import WordPressClient


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cleanup-paralelo")


def get_finalizadas(db_path: str, min_days: int = 0) -> list[dict]:
    """Devuelve subastas activas con fecha_conclusion vencida."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cutoff = f"-{min_days} days" if min_days > 0 else "now"
    cursor = conn.execute(
        f"""
        SELECT id_subasta, wp_post_id, fecha_conclusion, estado
        FROM subastas
        WHERE activa = 1
          AND fecha_conclusion IS NOT NULL
          AND datetime(fecha_conclusion) < datetime('{cutoff}')
        ORDER BY fecha_conclusion ASC
        """
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def despublicar_post(client: WordPressClient, post_id: int, hard_delete: bool) -> tuple[int, int]:
    """Despublica un post. Devuelve (post_id, status_code).

    - hard_delete=False: PUT status=draft (mantiene URLs por SEO/redirección)
    - hard_delete=True : DELETE force=true (borrado permanente)
    """
    try:
        if hard_delete:
            response = requests.delete(
                f"{client.api_url}/posts/{post_id}",
                headers=client.headers,
                params={"force": "true"},
                timeout=30,
            )
        else:
            response = requests.put(
                f"{client.api_url}/posts/{post_id}",
                headers=client.headers,
                json={"status": "draft", "meta": {"_subasta_estado": "Finalizada"}},
                timeout=30,
            )
        return post_id, response.status_code
    except requests.RequestException as e:
        logger.error(f"Error con post {post_id}: {e}")
        return post_id, 0


def marcar_inactivas_en_bd(db_path: str, ids_subasta: list[str]):
    """Marca un lote de subastas como inactivas y estado=Finalizada."""
    if not ids_subasta:
        return
    conn = sqlite3.connect(db_path)
    placeholders = ",".join("?" * len(ids_subasta))
    conn.execute(
        f"""
        UPDATE subastas
        SET activa = 0, estado = 'Finalizada', fecha_actualizacion = ?
        WHERE id_subasta IN ({placeholders})
        """,
        [datetime.now().isoformat(), *ids_subasta],
    )
    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Aplicar cambios (sin él, dry-run)")
    parser.add_argument("--delete", action="store_true",
                        help="DELETE permanente en lugar de pasar a borrador")
    parser.add_argument("--workers", type=int, default=5, help="Hilos paralelos")
    parser.add_argument("--min-days", type=int, default=0,
                        help="Solo subastas vencidas hace más de N días")
    parser.add_argument("--limit", type=int, default=0, help="Limitar nº (debug)")
    parser.add_argument("--yes", action="store_true", help="Sin confirmación interactiva")
    args = parser.parse_args()

    finalizadas = get_finalizadas(settings.DB_PATH, args.min_days)
    if args.limit:
        finalizadas = finalizadas[: args.limit]

    con_post = [f for f in finalizadas if f["wp_post_id"]]
    sin_post = [f for f in finalizadas if not f["wp_post_id"]]

    logger.info(f"Subastas finalizadas a procesar: {len(finalizadas)}")
    logger.info(f"  con wp_post_id: {len(con_post)}")
    logger.info(f"  sin wp_post_id (solo BD): {len(sin_post)}")

    if not finalizadas:
        return

    accion = "BORRAR PERMANENTE" if args.delete else "PASAR A BORRADOR"
    print(f"\nAcción: {accion}")
    print(f"Posts WP afectados: {len(con_post)}")

    if not args.execute:
        print("\n[DRY-RUN] No se modifica nada. Usa --execute para aplicar.")
        print("\nMuestra de las primeras 5:")
        for f in finalizadas[:5]:
            print(f"  {f['id_subasta']} | wp={f['wp_post_id']} | concluyó {f['fecha_conclusion']}")
        return

    if not args.yes:
        confirm = input(f"\n¿Confirmar {accion} de {len(con_post)} posts? [escribe 'SI']: ")
        if confirm != "SI":
            print("Cancelado.")
            return

    client = WordPressClient()
    ok_ids = []
    fail = []
    start = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_id = {
            executor.submit(despublicar_post, client, f["wp_post_id"], args.delete): f["id_subasta"]
            for f in con_post
        }
        for i, future in enumerate(as_completed(future_to_id), 1):
            id_sub = future_to_id[future]
            post_id, status = future.result()
            if status in (200, 410):
                ok_ids.append(id_sub)
            else:
                fail.append((id_sub, post_id, status))
            if i % 50 == 0:
                rate = i / (time.time() - start)
                eta = (len(con_post) - i) / rate if rate > 0 else 0
                logger.info(f"  {i}/{len(con_post)} ({rate:.1f}/s, ETA {eta/60:.0f}min)")

    duracion = time.time() - start
    logger.info(f"WP completo: {len(ok_ids)} OK, {len(fail)} fallos en {duracion/60:.1f}min")

    # Marcar todas las procesadas como inactivas en BD (incluyendo las sin post)
    todas_para_bd = ok_ids + [f["id_subasta"] for f in sin_post]
    marcar_inactivas_en_bd(settings.DB_PATH, todas_para_bd)
    logger.info(f"BD: {len(todas_para_bd)} subastas marcadas como inactivas")

    if fail:
        print(f"\nPrimeros 10 fallos:")
        for id_sub, post_id, status in fail[:10]:
            print(f"  {id_sub} (post {post_id}): HTTP {status}")


if __name__ == "__main__":
    main()
