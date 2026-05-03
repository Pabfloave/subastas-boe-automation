#!/usr/bin/env python3
"""
Genera un archivo SQL listo para pegar/importar en phpMyAdmin de Hostinger
que despublica TODOS los posts duplicados de subastas (mantiene el más
reciente por id_subasta).

Equivalente a `dedup_wp_posts.py dedup --mode draft` pero ejecutándose
directamente en MySQL → segundos en lugar de horas.

Uso:
    python scripts/generate_dedup_sql.py
    # → escribe scripts/dedup_despublicar.sql
"""
import json
from pathlib import Path

INVENTORY = Path(__file__).parent / "wp_inventory.json"
OUTPUT = Path(__file__).parent / "dedup_despublicar.sql"
BATCH_SIZE = 5000  # IDs por UPDATE (phpMyAdmin manejable)


def main():
    inv = json.loads(INVENTORY.read_text())
    by_id = inv["by_id"]

    posts_a_despublicar = []
    survivors = {}

    for id_sub, posts in by_id.items():
        if len(posts) <= 1:
            continue
        # Mantener el más reciente (mayor modified, luego mayor ID)
        posts_sorted = sorted(
            posts,
            key=lambda p: (p.get("modified", ""), p["id"]),
            reverse=True,
        )
        survivors[id_sub] = posts_sorted[0]["id"]
        for p in posts_sorted[1:]:
            posts_a_despublicar.append(p["id"])

    posts_a_despublicar.sort()
    print(f"Posts a despublicar: {len(posts_a_despublicar):,}")
    print(f"Subastas afectadas: {len(survivors):,}")
    print(f"Bloques de {BATCH_SIZE}: {(len(posts_a_despublicar) + BATCH_SIZE - 1) // BATCH_SIZE}")

    with OUTPUT.open("w") as f:
        f.write(f"""-- =====================================================================
-- Despublicado masivo de duplicados de subastas BOE
-- Generado: {inv['summary']['scanned_at']}
-- Total posts a despublicar: {len(posts_a_despublicar):,}
-- Subastas afectadas: {len(survivors):,}
-- Posts sobrevivientes (NO se tocan): los más recientes por id_subasta
--
-- Ejecuta este archivo entero en phpMyAdmin (Importar) o pega cada
-- bloque por separado en SQL → Ejecutar.
--
-- Acción: pasa el post_status de 'publish' a 'draft' (no borra nada).
-- Si algo va mal, puedes revertir con:
--   UPDATE wp_posts SET post_status='publish' WHERE post_status='draft' AND ID IN (...);
-- =====================================================================

-- Verificación previa (opcional): contar publicados antes
SELECT COUNT(*) AS publicados_antes FROM wp_posts WHERE post_status='publish';

START TRANSACTION;

""")

        for i in range(0, len(posts_a_despublicar), BATCH_SIZE):
            batch = posts_a_despublicar[i : i + BATCH_SIZE]
            ids_str = ",".join(str(x) for x in batch)
            f.write(
                f"-- Bloque {i // BATCH_SIZE + 1}/"
                f"{(len(posts_a_despublicar) + BATCH_SIZE - 1) // BATCH_SIZE} "
                f"({len(batch)} posts)\n"
            )
            f.write(
                f"UPDATE wp_posts SET post_status='draft' "
                f"WHERE post_status='publish' AND ID IN ({ids_str});\n\n"
            )

        f.write("""-- Verificación final
SELECT COUNT(*) AS publicados_despues FROM wp_posts WHERE post_status='publish';
SELECT COUNT(*) AS borradores FROM wp_posts WHERE post_status='draft';

-- Si todo OK, confirma:
COMMIT;

-- Si algo está mal, ejecuta esto en su lugar:
-- ROLLBACK;
""")

    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"\n✓ Archivo generado: {OUTPUT}")
    print(f"  Tamaño: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
