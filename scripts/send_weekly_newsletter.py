#!/usr/bin/env python3
"""
Envío semanal de la newsletter "Subastas BOE de la semana".

Pipeline:
  1. Lee subscribers activos desde el plugin WP (REST API + X-API-Key).
  2. Selecciona top 10 subastas activas de SQLite local con filtros básicos:
       - estado activa = 1
       - valor de tipo entre NEWSLETTER_PRICE_MIN y NEWSLETTER_PRICE_MAX
       - prioriza provincias top o la provincia preferida del subscriber.
  3. Renderiza el template Jinja2 (content/templates/newsletter-weekly.html).
  4. Envía vía SMTP a cada subscriber, con UTM tracking y unsubscribe token.
  5. Loggea resultados.

Variables .env necesarias:
  WP_URL, CAFAVE_LM_API_KEY,
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM,
  NEWSLETTER_PRICE_MIN=50000, NEWSLETTER_PRICE_MAX=500000

Uso:
  python scripts/send_weekly_newsletter.py            # envío real
  python scripts/send_weekly_newsletter.py --dry-run  # render + guarda HTML, no envía
  python scripts/send_weekly_newsletter.py --test-email me@example.com
  python scripts/send_weekly_newsletter.py --limit 5  # primeros 5 subscribers

Cron sugerido (lunes 9:00):
  0 9 * * 1 cd ~/subastas-boe-automation && /usr/bin/python3 scripts/send_weekly_newsletter.py >> data/logs/newsletter.log 2>&1
"""
from __future__ import annotations

import argparse
import logging
import os
import smtplib
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.provinces import PROVINCIAS_ESPANA  # noqa: E402

load_dotenv(BASE_DIR / ".env")

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "subastas.db"))
WP_URL = os.getenv("WP_URL", "https://comprarensubasta.com").rstrip("/")
API_KEY = os.getenv("CAFAVE_LM_API_KEY", "")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", f"CAFAVE Investment <noreply@{WP_URL.split('//')[-1]}>")

PRICE_MIN = int(os.getenv("NEWSLETTER_PRICE_MIN", "50000"))
PRICE_MAX = int(os.getenv("NEWSLETTER_PRICE_MAX", "500000"))
TOP_PROVINCES = ["28", "08", "46", "41", "29", "30", "03", "11"]  # Madrid, BCN, VLC, SVQ, MLG, MUR, ALC, CDZ

CHECKLIST_URL = f"{WP_URL}/recursos/checklist-47-puntos"
INFORME_LANDING = f"{WP_URL}/informe-juridico-subasta"
PRIVACY_URL = f"{WP_URL}/aviso-legal"
TEMPLATE_DIR = BASE_DIR / "content" / "templates"
DRY_OUTPUT_DIR = BASE_DIR / "data" / "newsletters"

LOG_DIR = BASE_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "newsletter.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("newsletter")


# ──────────────────────────────────────────────
# Selection of top 10 subastas
# ──────────────────────────────────────────────
def select_top_subastas(
    conn: sqlite3.Connection,
    limit: int = 10,
    provincia_preferida: str | None = None,
) -> list[dict]:
    """
    Selecciona top N subastas activas con joins a bienes.

    Estrategia:
      - estado activa = 1 (y publicado_wp = 1, para tener URL)
      - valor de tipo (valor_subasta_lote o fallback subasta.valor_subasta) en rango
      - prioriza la provincia preferida; si no hay suficientes, completa con top provinces
      - ordena por proximidad de fecha_conclusion (urgencia)
    """
    cur = conn.cursor()
    base_query = """
        SELECT
          s.id_subasta, s.tipo_subasta, s.valor_subasta, s.importe_deposito,
          s.fecha_inicio, s.fecha_conclusion, s.wp_post_id,
          b.tipo_bien, b.direccion, b.localidad, b.provincia, b.provincia_codigo,
          b.valor_subasta_lote, b.importe_deposito_lote
        FROM subastas s
        JOIN bienes b ON b.id_subasta = s.id_subasta
        WHERE s.activa = 1
          AND s.publicado_wp = 1
          AND s.wp_post_id IS NOT NULL
          AND COALESCE(b.valor_subasta_lote, s.valor_subasta) BETWEEN ? AND ?
    """
    params: list = [PRICE_MIN, PRICE_MAX]

    if provincia_preferida:
        query = base_query + " AND b.provincia_codigo = ? ORDER BY s.fecha_conclusion ASC LIMIT ?"
        params.extend([provincia_preferida, limit])
    else:
        placeholders = ",".join("?" * len(TOP_PROVINCES))
        query = (
            base_query
            + f" AND b.provincia_codigo IN ({placeholders})"
            + " ORDER BY s.fecha_conclusion ASC LIMIT ?"
        )
        params.extend(TOP_PROVINCES)
        params.append(limit)

    rows = [dict(r) for r in cur.execute(query, params).fetchall()]

    # Fallback: si la provincia preferida no devolvió suficientes, completa con top provinces
    if provincia_preferida and len(rows) < limit:
        missing = limit - len(rows)
        seen = {r["id_subasta"] for r in rows}
        placeholders = ",".join("?" * len(TOP_PROVINCES))
        fb_query = (
            base_query
            + f" AND b.provincia_codigo IN ({placeholders})"
            + " ORDER BY s.fecha_conclusion ASC LIMIT ?"
        )
        fb_params: list = [PRICE_MIN, PRICE_MAX]
        fb_params.extend(TOP_PROVINCES)
        fb_params.append(missing + len(seen))
        for r in (dict(x) for x in cur.execute(fb_query, fb_params).fetchall()):
            if r["id_subasta"] not in seen:
                rows.append(r)
                if len(rows) >= limit:
                    break

    return rows


def _human_euro(value: float | int | None) -> str:
    if not value:
        return "—"
    return f"{int(value):,}".replace(",", ".")


def _format_date(dt_str: str | None) -> str:
    if not dt_str:
        return ""
    try:
        d = datetime.fromisoformat(dt_str)
        meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
        return f"{d.day} {meses[d.month - 1]} {d.year}"
    except (ValueError, TypeError):
        return ""


def _build_wp_url_from_id(post_id: int, utm_suffix: str) -> str:
    return f"{WP_URL}/?p={post_id}&{utm_suffix}"


def shape_subasta_for_template(row: dict, utm_suffix: str) -> dict:
    """Adapta una fila SQL al shape esperado por el template Jinja2."""
    valor = row.get("valor_subasta_lote") or row.get("valor_subasta") or 0
    deposito = row.get("importe_deposito_lote") or row.get("importe_deposito") or (valor * 0.05)

    direccion_parts: list[str] = []
    if row.get("direccion"):
        direccion_parts.append(row["direccion"])
    if row.get("localidad"):
        direccion_parts.append(row["localidad"])

    titulo = (
        f"{(row.get('tipo_bien') or 'Inmueble').capitalize()} en "
        f"{row.get('localidad') or row.get('provincia') or 'España'}"
    )

    return {
        "id_subasta": row["id_subasta"],
        "titulo": titulo,
        "provincia": row.get("provincia") or "—",
        "tipo_bien": (row.get("tipo_bien") or "Inmueble").capitalize(),
        "direccion": ", ".join(direccion_parts),
        "valor_human": _human_euro(valor),
        "deposito_human": _human_euro(deposito),
        "fecha_fin": _format_date(row.get("fecha_conclusion")),
        "wp_url": _build_wp_url_from_id(int(row["wp_post_id"]), utm_suffix),
        "informe_url": f"{INFORME_LANDING}?activo={row['id_subasta']}&{utm_suffix}",
    }


# ──────────────────────────────────────────────
# Subscribers fetching
# ──────────────────────────────────────────────
def fetch_subscribers() -> list[dict]:
    if not API_KEY:
        raise SystemExit("ERROR: CAFAVE_LM_API_KEY not set in .env")
    url = f"{WP_URL}/wp-json/cafave/v1/newsletter/subscribers"
    r = requests.get(url, headers={"X-API-Key": API_KEY}, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("subscribers", [])


# ──────────────────────────────────────────────
# Rendering
# ──────────────────────────────────────────────
def render_email(
    env: Environment,
    subscriber: dict,
    subastas: list[dict],
    week_label: str,
) -> str:
    utm_suffix = urlencode(
        {
            "utm_source": "newsletter",
            "utm_medium": "email",
            "utm_campaign": "weekly",
            "utm_content": week_label.replace(" ", "-").lower(),
        }
    )

    unsubscribe_url = f"{WP_URL}/wp-json/cafave/v1/newsletter/unsubscribe?token={subscriber['unsubscribe_token']}"
    informe_landing = f"{INFORME_LANDING}?{utm_suffix}"
    checklist_url = f"{CHECKLIST_URL}?{utm_suffix}"

    shaped = [shape_subasta_for_template(s, utm_suffix) for s in subastas]

    template = env.get_template("newsletter-weekly.html")
    return template.render(
        week_label=week_label,
        preheader=f"{len(shaped)} subastas seleccionadas esta semana · {week_label}",
        total_count=len(shaped),
        subastas=shaped,
        site_url=WP_URL,
        checklist_url=checklist_url,
        informe_landing_url=informe_landing,
        unsubscribe_url=unsubscribe_url,
        privacy_url=PRIVACY_URL,
        price_min_human=_human_euro(PRICE_MIN),
        price_max_human=_human_euro(PRICE_MAX),
    )


# ──────────────────────────────────────────────
# SMTP delivery
# ──────────────────────────────────────────────
def smtp_send(server: smtplib.SMTP, recipient: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = recipient
    msg["Message-ID"] = make_msgid(domain=WP_URL.split("//")[-1])
    msg["List-Unsubscribe"] = f"<mailto:unsubscribe@{WP_URL.split('//')[-1]}>"
    msg.attach(MIMEText(html, "html", "utf-8"))
    server.sendmail(SMTP_FROM, [recipient], msg.as_string())


def open_smtp() -> smtplib.SMTP:
    if not SMTP_HOST or not SMTP_USER:
        raise SystemExit("ERROR: SMTP_HOST / SMTP_USER not configured in .env")
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
    server.ehlo()
    if SMTP_PORT == 587:
        server.starttls()
        server.ehlo()
    server.login(SMTP_USER, SMTP_PASS)
    return server


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="render y guarda HTML, no envía")
    ap.add_argument("--test-email", help="envía solo a este email (ignora la lista de subscribers)")
    ap.add_argument("--limit", type=int, default=None, help="limitar nº de subscribers a procesar")
    args = ap.parse_args()

    if not Path(DB_PATH).exists():
        log.error("Database not found: %s", DB_PATH)
        return 1

    week_label = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("Semana del %d/%m/%Y")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Recolectar subscribers
    if args.test_email:
        subscribers = [{"email": args.test_email, "provincia_pref": None, "unsubscribe_token": "TEST"}]
        log.info("Test mode: %s", args.test_email)
    else:
        try:
            subscribers = fetch_subscribers()
        except requests.HTTPError as e:
            log.error("Failed to fetch subscribers: %s", e)
            return 1
        log.info("Fetched %d active subscribers", len(subscribers))

    if args.limit:
        subscribers = subscribers[: args.limit]

    if not subscribers:
        log.warning("No subscribers to send to. Exiting.")
        return 0

    # Pre-fetch generic top 10 (sin provincia) — sirve a la mayoría
    generic_top10 = select_top_subastas(conn, limit=10)
    if not generic_top10:
        log.error("No subastas found matching the criteria. Aborting send.")
        return 1
    log.info("Pre-fetched %d generic subastas for newsletter", len(generic_top10))

    # SMTP connection (lazy if dry-run)
    server: smtplib.SMTP | None = None
    if not args.dry_run:
        server = open_smtp()
        log.info("SMTP connected to %s:%d", SMTP_HOST, SMTP_PORT)

    sent, failed = 0, 0
    subject = f"Subastas BOE de la semana — {week_label}"

    DRY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for idx, sub in enumerate(subscribers, start=1):
        email = sub["email"]
        try:
            top10 = generic_top10
            if sub.get("provincia_pref"):
                personalized = select_top_subastas(
                    conn, limit=10, provincia_preferida=sub["provincia_pref"]
                )
                if personalized:
                    top10 = personalized

            html = render_email(env, sub, top10, week_label)

            if args.dry_run:
                out = DRY_OUTPUT_DIR / f"preview-{idx:03d}-{email.replace('@', '_at_')}.html"
                out.write_text(html, encoding="utf-8")
                log.info("[DRY] %s -> %s", email, out.name)
                sent += 1
            else:
                smtp_send(server, email, subject, html)
                sent += 1
                if sent % 25 == 0:
                    log.info("Sent %d so far…", sent)
                time.sleep(0.4)  # rate limit: ~150 emails/min
        except Exception as e:
            failed += 1
            log.error("Failed to send to %s: %s", email, e)

    if server:
        server.quit()

    log.info("Done. Sent: %d · Failed: %d · Total: %d", sent, failed, len(subscribers))
    conn.close()
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
