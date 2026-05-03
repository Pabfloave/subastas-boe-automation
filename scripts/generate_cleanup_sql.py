#!/usr/bin/env python3
"""
Genera SQL para despublicar (status=draft) las subastas cuya
fecha_conclusion ya pasó.

Uso:
    python scripts/generate_cleanup_sql.py
    # → escribe scripts/cleanup_finalizadas.sql
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings


OUTPUT = Path(__file__).parent / "cleanup_finalizadas.sql"
BATCH_SIZE = 5000


def main():
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT id_subasta, wp_post_id, fecha_conclusion
        FROM subastas
        WHERE activa = 1
          AND wp_post_id IS NOT NULL
          AND fecha_conclusion IS NOT NULL
          AND datetime(fecha_conclusion) < datetime('now')
        ORDER BY fecha_conclusion ASC
        """
    ).fetchall()
    conn.close()

    wp_ids = sorted({r["wp_post_id"] for r in rows})
    print(f"Subastas finalizadas con wp_post_id: {len(rows)}")
    print(f"wp_post_ids únicos a despublicar: {len(wp_ids)}")
    print(f"Bloques de {BATCH_SIZE}: {(len(wp_ids) + BATCH_SIZE - 1) // BATCH_SIZE}")

    if not wp_ids:
        print("Nada que despublicar.")
        return

    with OUTPUT.open("w") as f:
        f.write(f"""-- =====================================================================
-- Despublicado de subastas BOE FINALIZADAS por fecha_conclusion
-- Total wp_post_ids: {len(wp_ids):,}
-- Acción: post_status='publish' → post_status='draft' (recuperable)
-- =====================================================================

-- Verificación previa
SELECT COUNT(*) AS publicados_antes FROM wp_posts WHERE post_status='publish';

START TRANSACTION;

""")

        for i in range(0, len(wp_ids), BATCH_SIZE):
            batch = wp_ids[i : i + BATCH_SIZE]
            ids_str = ",".join(str(x) for x in batch)
            f.write(
                f"-- Bloque {i // BATCH_SIZE + 1}/"
                f"{(len(wp_ids) + BATCH_SIZE - 1) // BATCH_SIZE} "
                f"({len(batch)} posts)\n"
            )
            f.write(
                f"UPDATE wp_posts SET post_status='draft' "
                f"WHERE post_status='publish' AND ID IN ({ids_str});\n\n"
            )

        f.write("""-- Verificación final
SELECT COUNT(*) AS publicados_despues FROM wp_posts WHERE post_status='publish';

COMMIT;
""")

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"\n✓ Archivo generado: {OUTPUT}")
    print(f"  Tamaño: {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
