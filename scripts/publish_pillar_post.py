#!/usr/bin/env python3
"""
Publica el post pillar #001 en comprarensubasta.com.

Lee `content/post-001-borrador.md` (frontmatter YAML-ish + Markdown),
lo convierte a HTML SEO-friendly, genera FAQ JSON-LD inline y crea el post
como draft via WP REST API.

Uso:
    python3 scripts/publish_pillar_post.py            # draft (por defecto)
    python3 scripts/publish_pillar_post.py --publish  # publica directo
"""
import argparse
import base64
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD_FILE = ROOT / "content" / "post-001-borrador.md"


def load_env():
    """Carga variables del .env del proyecto padre (mismo patrón del repo)."""
    for candidate in (ROOT / ".env", ROOT.parent.parent.parent / ".env"):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return candidate
    return None


ENV_PATH = load_env()
SITE_URL = os.environ.get("WP_URL", "https://comprarensubasta.com").rstrip("/")
WP_USER = os.environ.get("WP_USER", "")
WP_PWD = os.environ.get("WP_APP_PASSWORD", "")
CTA_PRIMARY_URL = os.environ.get("WP_CONTACT_FORM_URL", f"{SITE_URL}/#analisis")
API = f"{SITE_URL}/wp-json/wp/v2"


def wp_request(method: str, path: str, body: dict | None = None, params: dict | None = None) -> dict | list:
    url = f"{API}/{path.lstrip('/')}"
    if params:
        q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url += ("?" + q)
    data = json.dumps(body).encode() if body is not None else None
    auth = base64.b64encode(f"{WP_USER}:{WP_PWD}".encode()).decode()
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"WP {method} {path} {e.code}: {msg}") from e


import urllib.parse  # noqa: E402


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 5:]
    fm: dict = {}
    current_list_key = None
    for line in fm_text.split("\n"):
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list_key:
            fm[current_list_key].append(line[4:].strip().strip('"'))
            continue
        m = re.match(r"^([a-z_][\w_]*):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "":
            fm[key] = []
            current_list_key = key
        else:
            fm[key] = val.strip('"')
            current_list_key = None
    return fm, body


def inline_md(text: str) -> str:
    """Convierte sintaxis inline de Markdown a HTML."""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def md_table_to_html(rows: list[str]) -> str:
    cells = [
        [c.strip() for c in r.strip().strip("|").split("|")]
        for r in rows
    ]
    head = cells[0]
    body = cells[2:] if len(cells) > 2 else []
    html = ['<figure class="wp-block-table"><table>']
    html.append("<thead><tr>")
    for c in head:
        html.append(f"<th>{inline_md(c)}</th>")
    html.append("</tr></thead><tbody>")
    for row in body:
        html.append("<tr>")
        for c in row:
            html.append(f"<td>{inline_md(c)}</td>")
        html.append("</tr>")
    html.append("</tbody></table></figure>")
    return "".join(html)


def strip_md(text: str) -> str:
    """Quita marcas Markdown inline para texto plano (schema)."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def md_body_to_html(body: str) -> tuple[str, list[dict]]:
    """Convierte el cuerpo Markdown a HTML.

    Devuelve (html, faqs) donde faqs es la lista de Q/A (texto plano) de la
    sección "Preguntas frecuentes" — usadas para generar el JSON-LD FAQPage.
    Las FAQs también se renderizan como HTML visible en el post.
    """
    lines = body.split("\n")
    out: list[str] = []
    faqs: list[dict] = []
    in_faq_section = False
    current_q: str | None = None
    current_a: list[str] = []
    i = 0

    def flush_faq():
        nonlocal current_q, current_a
        if current_q and current_a:
            answer_raw = " ".join(current_a).strip()
            faqs.append({"q": strip_md(current_q), "a": strip_md(answer_raw)})
            out.append(f"<h3>{inline_md(current_q)}</h3>")
            out.append(f"<p>{inline_md(answer_raw)}</p>")
        current_q = None
        current_a = []

    while i < len(lines):
        line = lines[i]

        # H1 (título) — lo omitimos, lo da WP
        if line.startswith("# ") and not line.startswith("## "):
            i += 1
            continue

        # H2
        if line.startswith("## "):
            flush_faq()
            title = line[3:].strip()
            in_faq_section = title.lower().startswith("preguntas frecuentes")
            out.append(f"<h2>{inline_md(title)}</h2>")
            i += 1
            continue

        # H3
        if line.startswith("### "):
            title = line[4:].strip()
            if in_faq_section:
                flush_faq()
                current_q = title
                i += 1
                continue
            out.append(f"<h3>{inline_md(title)}</h3>")
            i += 1
            continue

        # Tabla (cabecera contiene | y la siguiente línea es separador |---|)
        if line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s|:-]+\|\s*$", lines[i + 1]):
            tbl_rows = [line]
            j = i + 1
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                tbl_rows.append(lines[j])
                j += 1
            out.append(md_table_to_html(tbl_rows))
            i = j
            continue

        # Blockquote (puede ser multi-línea consecutiva)
        if line.startswith("> "):
            bq_lines = []
            while i < len(lines) and lines[i].startswith("> "):
                bq_lines.append(lines[i][2:])
                i += 1
            inner = inline_md(" ".join(bq_lines).strip())
            out.append(f"<blockquote><p>{inner}</p></blockquote>")
            continue

        # HR
        if line.strip() == "---":
            flush_faq()
            out.append("<hr>")
            i += 1
            continue

        # Lista ordenada
        if re.match(r"^\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i]))
                i += 1
            out.append("<ol>")
            for it in items:
                out.append(f"<li>{inline_md(it)}</li>")
            out.append("</ol>")
            continue

        # Lista no ordenada
        if re.match(r"^[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i]):
                items.append(re.sub(r"^[-*]\s+", "", lines[i]))
                i += 1
            out.append("<ul>")
            for it in items:
                out.append(f"<li>{inline_md(it)}</li>")
            out.append("</ul>")
            continue

        # Línea vacía
        if not line.strip():
            i += 1
            continue

        # Párrafo (acumula líneas consecutivas no especiales)
        para = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if (
                not nxt.strip()
                or nxt.startswith("#")
                or nxt.startswith(">")
                or nxt.startswith("|")
                or nxt.startswith("---")
                or re.match(r"^\d+\.\s+", nxt)
                or re.match(r"^[-*]\s+", nxt)
            ):
                break
            para.append(nxt)
            i += 1
        text = " ".join(p.strip() for p in para)
        if in_faq_section and current_q is not None:
            current_a.append(text)
        else:
            out.append(f"<p>{inline_md(text)}</p>")

    flush_faq()
    return "\n".join(out), faqs


def build_faq_schema(faqs: list[dict]) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f["q"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": re.sub(r"<[^>]+>", "", f["a"]),
                },
            }
            for f in faqs
        ],
    }
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(schema, ensure_ascii=False, indent=2)
        + "\n</script>"
    )


def build_article_schema(fm: dict, post_url_placeholder: str) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": fm["title"],
        "description": fm["meta_description"],
        "author": {"@type": "Organization", "name": fm.get("author", "CAFAVE Investment")},
        "publisher": {
            "@type": "Organization",
            "name": "Comprar en Subasta",
            "url": SITE_URL,
        },
        "datePublished": fm.get("date", ""),
        "mainEntityOfPage": post_url_placeholder,
    }
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(schema, ensure_ascii=False, indent=2)
        + "\n</script>"
    )


def rewrite_internal_ctas(html: str) -> str:
    """Sustituye URLs internas inexistentes por el form home `#analisis`.

    El borrador apunta a /informe-juridico-subasta (404 actualmente).
    """
    return html.replace(
        'href="/informe-juridico-subasta"',
        f'href="{CTA_PRIMARY_URL}"',
    )


def build_final_html(fm: dict, body_html: str, faqs: list[dict]) -> str:
    body_html = rewrite_internal_ctas(body_html)
    parts = [body_html]

    if faqs:
        parts.append(build_faq_schema(faqs))

    parts.append(build_article_schema(fm, f"{SITE_URL}/{fm['slug']}/"))

    return "\n\n".join(parts)


def get_or_create_term(taxonomy: str, name: str, slug: str | None = None) -> int:
    """Busca o crea una categoría/tag. taxonomy: 'categories' o 'tags'."""
    existing = wp_request("GET", taxonomy, params={"search": name, "per_page": 100})
    for term in existing:
        if term["name"].lower() == name.lower() or (slug and term["slug"] == slug):
            return term["id"]
    body = {"name": name}
    if slug:
        body["slug"] = slug
    created = wp_request("POST", taxonomy, body=body)
    print(f"  · creado {taxonomy[:-1]}: {name} (id={created['id']})")
    return created["id"]


def publish(fm: dict, html: str, status: str) -> dict:
    if not (WP_USER and WP_PWD):
        raise RuntimeError("WP_USER/WP_APP_PASSWORD no encontrados en .env")

    cat_guias = get_or_create_term("categories", "Guías", slug="guias")

    tag_ids = []
    for name in ["cargas", "subasta judicial", "due diligence", "ley hipotecaria", "guia-evergreen"]:
        tag_ids.append(get_or_create_term("tags", name))

    meta = {
        "rank_math_focus_keyword": fm.get("focus_keyword", ""),
        "rank_math_description": fm.get("meta_description", ""),
        "rank_math_title": fm["title"],
        "rank_math_canonical_url": "",
        "rank_math_rich_snippet": "off",
        "_yoast_wpseo_metadesc": fm.get("meta_description", ""),
        "_yoast_wpseo_focuskw": fm.get("focus_keyword", ""),
    }

    return wp_request("POST", "posts", body={
        "title": fm["title"],
        "content": html,
        "status": status,
        "slug": fm["slug"],
        "categories": [cat_guias],
        "tags": tag_ids,
        "meta": meta,
    })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true", help="Publicar (default: draft)")
    parser.add_argument("--dry-run", action="store_true", help="Solo imprimir HTML, no publicar")
    args = parser.parse_args()

    status = "publish" if args.publish else "draft"
    raw = MD_FILE.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)

    for required in ("title", "slug", "meta_description"):
        if required not in fm:
            raise ValueError(f"Falta '{required}' en frontmatter")

    body_html, faqs = md_body_to_html(body)
    final_html = build_final_html(fm, body_html, faqs)

    print(f"Título: {fm['title']}")
    print(f"Slug:   {fm['slug']}")
    print(f"FAQs:   {len(faqs)}")
    print(f"HTML:   {len(final_html)} bytes")

    if args.dry_run:
        out = ROOT / "content" / "post-001-render.html"
        out.write_text(final_html, encoding="utf-8")
        print(f"\n--dry-run: HTML escrito en {out}")
        return

    result = publish(fm, final_html, status)
    print(f"\n✓ Post {status.upper()}: ID {result['id']}")
    print(f"  Link (preview): {result.get('link')}")
    print(f"  Edit:           {SITE_URL}/wp-admin/post.php?post={result['id']}&action=edit")


if __name__ == "__main__":
    main()
