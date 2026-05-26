#!/usr/bin/env python3
"""
Genera el PDF "Checklist 47 puntos antes de pujar" desde el markdown fuente.

Pipeline:
  content/lead-magnet-checklist-47-puntos.md
    -> parseo a HTML semántico (con clase .item para cada punto)
    -> render Jinja2 con content/templates/checklist-pdf.html
    -> WeasyPrint -> content/lead-magnets/checklist-47-puntos.pdf

Uso:
  python scripts/build_checklist_pdf.py

Dependencias del sistema (macOS):
  brew install pango libffi gdk-pixbuf
"""
import re
import sys
import datetime as dt
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
MARKDOWN_SRC = BASE_DIR / "content" / "lead-magnet-checklist-47-puntos.md"
TEMPLATE_PATH = BASE_DIR / "content" / "templates" / "checklist-pdf.html"
OUTPUT_PDF = BASE_DIR / "content" / "lead-magnets" / "checklist-47-puntos.pdf"


def parse_markdown_to_html(md_text: str) -> str:
    """
    Convierte el markdown del checklist a HTML semántico.

    Reconoce 3 patrones del documento:
      1. Bloques de "**A1. Enunciado.**\n Nota legal" -> div.item
      2. Cajas "## Bloque ..." -> h2
      3. Resto: párrafos, hrs, listas, etc.

    No es un parser markdown genérico — está adaptado al formato del
    checklist concreto. Mantiene el código simple y predecible.
    """
    # Drop the YAML front-matter
    if md_text.startswith("---"):
        md_text = md_text.split("---", 2)[2]

    lines = md_text.split("\n")
    html_parts: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()

        # h1
        if line.startswith("# "):
            html_parts.append(f"<h1>{_inline(line[2:])}</h1>")
            i += 1
            continue

        # h2
        if line.startswith("## "):
            html_parts.append(f"<h2>{_inline(line[3:])}</h2>")
            i += 1
            continue

        # h3
        if line.startswith("### "):
            html_parts.append(f"<h3>{_inline(line[4:])}</h3>")
            i += 1
            continue

        # hr
        if line.strip() == "---":
            html_parts.append("<hr/>")
            i += 1
            continue

        # Checklist item: starts with "**A1. ...**" or similar
        item_match = re.match(r"^\*\*([A-E]\d+)\.\s+(.+?)\*\*\s*$", line)
        if item_match:
            code, title = item_match.groups()
            # Nota legal = siguientes líneas no-vacías hasta línea vacía
            j = i + 1
            note_lines: list[str] = []
            while j < len(lines) and lines[j].strip() != "":
                note_lines.append(lines[j].strip())
                j += 1
            note = " ".join(note_lines)
            html_parts.append(
                f'<div class="item">'
                f'<span class="item-title">{code}. {_inline(title)}</span>'
                f'<p class="item-note">{_inline(note)}</p>'
                f"</div>"
            )
            i = j
            continue

        # Bullet list
        if line.startswith("- "):
            items: list[str] = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{_inline(lines[i][2:])}</li>")
                i += 1
            html_parts.append("<ul>" + "".join(items) + "</ul>")
            continue

        # Blank line
        if line.strip() == "":
            i += 1
            continue

        # Plain paragraph: collect contiguous non-blank lines
        para_lines = [line]
        i += 1
        while i < len(lines) and lines[i].strip() != "" and not _is_special(lines[i]):
            para_lines.append(lines[i])
            i += 1
        paragraph = " ".join(_inline(p) for p in para_lines)

        # Detectar el bloque introductorio (negrita + texto)
        css_class = ""
        if paragraph.startswith("<strong>Esta guía recoge"):
            css_class = ' class="intro"'

        html_parts.append(f"<p{css_class}>{paragraph}</p>")

    full_html = "\n".join(html_parts)

    # Inyectar caja CTA (precio del informe). El footer legal está en el template,
    # así que también eliminamos el párrafo `*CAFAVE Investment...*` del markdown
    # para evitar duplicación.
    cta_html = (
        '<div class="cta">'
        "<h3>¿Necesitas un análisis caso por caso?</h3>"
        "<p>Solicita un informe jurídico previo personalizado sobre la subasta "
        "concreta que te interese. Firma de abogado colegiado, responsabilidad "
        "profesional, entrega en 48 horas hábiles.</p>"
        '<p><span class="price">72,60 € (IVA incl.)</span></p>'
        '<p>Más información: '
        '<a href="https://comprarensubasta.com/informe-juridico-subasta">'
        "comprarensubasta.com/informe-juridico-subasta</a></p>"
        "</div>"
    )

    # 1) Drop the body-level duplicated legal paragraph (lives in template footer).
    full_html = re.sub(
        r"<p><em>CAFAVE Investment.*?</em></p>\s*<p><em>Aviso legal:.*?</em></p>",
        "",
        full_html,
        flags=re.DOTALL,
    )

    # 2) Replace the plain-text CTA block (Tarifa fija + Solicítalo en…) with the styled CTA.
    full_html = re.sub(
        r"<p><strong>Tarifa fija:.*?</strong></p>\s*<p>Solicítalo en:.*?</p>",
        cta_html,
        full_html,
        flags=re.DOTALL,
    )

    return full_html


def _is_special(line: str) -> bool:
    """Returns True if line starts a heading, list item, hr, or checklist item."""
    s = line.lstrip()
    if s.startswith(("#", "- ", "---")):
        return True
    if re.match(r"^\*\*[A-E]\d+\.", s):
        return True
    return False


def _inline(text: str) -> str:
    """Inline markdown: **bold**, *italic*, [text](url), and `code`."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def build_pdf() -> Path:
    if not MARKDOWN_SRC.exists():
        raise SystemExit(f"ERROR: source markdown not found at {MARKDOWN_SRC}")
    if not TEMPLATE_PATH.exists():
        raise SystemExit(f"ERROR: template not found at {TEMPLATE_PATH}")

    try:
        from jinja2 import Template
        from weasyprint import HTML
    except ImportError as e:
        raise SystemExit(
            f"ERROR: missing dependency ({e.name}). "
            "Install: pip install -r requirements.txt "
            "and brew install pango libffi gdk-pixbuf (macOS) "
            "or apt install libpango-1.0-0 libpangoft2-1.0-0 (Debian)."
        )

    md_text = MARKDOWN_SRC.read_text(encoding="utf-8")
    body_html = parse_markdown_to_html(md_text)

    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    full_html = template.render(
        title="Checklist 47 puntos antes de pujar — CAFAVE",
        year=dt.date.today().year,
        body_html=body_html,
    )

    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=full_html, base_url=str(BASE_DIR)).write_pdf(target=str(OUTPUT_PDF))
    return OUTPUT_PDF


if __name__ == "__main__":
    out = build_pdf()
    size_kb = out.stat().st_size / 1024
    print(f"[OK] PDF generated: {out} ({size_kb:.1f} KB)")
