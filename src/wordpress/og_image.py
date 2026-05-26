"""
Generador local de imágenes Open Graph (OG) para posts de subastas.

Decisión D1 del PLAN_SEO.md: usamos Pillow en local en vez de Google Static
Maps. Cero coste, cero tracker externo, RGPD ok.

Pipeline:
1. `render_og_image(tipo, localidad, precio, provincia)` genera un JPEG
   1200×630 con los datos clave (cache determinista por sha1).
2. `upload_to_wordpress(local_path, client)` lo sube via REST `/wp/v2/media`
   y devuelve `{"id": int, "source_url": str}`. Se cachea por hash dentro
   del proceso para no duplicar uploads cuando el mismo tipo+localidad+precio
   se repite entre posts (muchas subastas comparten esta tupla → cache hit
   esperado >80%).
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Paleta alineada con el CSS del sitio (page_generator.py + publisher.py).
BG_COLOR = (15, 23, 42)        # --color-primary
ACCENT_COLOR = (217, 119, 6)   # --color-accent
TEXT_COLOR = (255, 255, 255)
MUTED_COLOR = (148, 163, 184)  # slate-400

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = ROOT / ".cache" / "og"
FONT_BOLD = ROOT / "assets" / "fonts" / "DMSans-Bold.ttf"
FONT_REGULAR = ROOT / "assets" / "fonts" / "DMSans-Regular.ttf"

# Tamaño OG estándar (Facebook, Twitter, LinkedIn comparten el ratio 1.91:1).
WIDTH, HEIGHT = 1200, 630

# Cache de uploads dentro del proceso: hash → URL pública en WP.
# Evita re-subir la misma imagen para subastas con tipo+localidad+precio
# idénticos durante un mismo `sync`.
_UPLOAD_CACHE: dict[str, dict] = {}


def _hash_key(tipo: str, localidad: str, precio_str: str) -> str:
    raw = f"{tipo}|{localidad}|{precio_str}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def render_og_image(
    tipo: str,
    localidad: str,
    precio_str: str,
    provincia: str = "",
) -> Optional[Path]:
    """Renderiza una imagen OG 1200×630 y devuelve la ruta local (cacheada).

    Si Pillow no está disponible, devuelve None y el caller debe usar un
    fallback (ej: og_image por defecto del sitio).
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow no instalado — OG image dinámica desactivada")
        return None

    if not FONT_BOLD.exists() or not FONT_REGULAR.exists():
        logger.warning(
            "Fonts no encontradas en assets/fonts/ — OG image dinámica desactivada"
        )
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _hash_key(tipo, localidad, precio_str)
    out = CACHE_DIR / f"{key}.jpg"
    if out.exists():
        return out

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    d = ImageDraw.Draw(img)

    f_xl = ImageFont.truetype(str(FONT_BOLD), 80)
    f_lg = ImageFont.truetype(str(FONT_BOLD), 56)
    f_md = ImageFont.truetype(str(FONT_REGULAR), 36)
    f_sm = ImageFont.truetype(str(FONT_REGULAR), 26)
    f_brand = ImageFont.truetype(str(FONT_BOLD), 28)

    # Banda lateral acento (touch visual).
    d.rectangle([(0, 0), (12, HEIGHT)], fill=ACCENT_COLOR)

    # Header: kicker "SUBASTA JUDICIAL"
    d.text((60, 60), "SUBASTA JUDICIAL", fill=ACCENT_COLOR, font=f_md)

    # Cuerpo: tipo (gran) + localidad (mediano)
    tipo_display = (tipo or "INMUEBLE").upper()
    d.text((60, 120), _truncate(tipo_display, 22), fill=TEXT_COLOR, font=f_xl)

    localidad_display = f"en {localidad}" if localidad else ""
    if localidad_display:
        d.text((60, 220), _truncate(localidad_display, 28), fill=TEXT_COLOR, font=f_lg)

    if provincia and provincia.lower() != localidad.lower():
        d.text((60, 300), provincia, fill=MUTED_COLOR, font=f_md)

    # Footer izquierda: bloque de precio
    d.text((60, 450), "VALOR DE SALIDA", fill=ACCENT_COLOR, font=f_sm)
    d.text((60, 490), _truncate(precio_str or "Consultar", 20), fill=TEXT_COLOR, font=f_lg)

    # Footer derecha: marca
    brand_text = "Comprar en Subasta"
    brand_w = _measure(d, brand_text, f_brand)
    d.text((WIDTH - brand_w - 60, 530), brand_text, fill=TEXT_COLOR, font=f_brand)

    sub_text = "CAFAVE INVESTMENT"
    sub_w = _measure(d, sub_text, f_sm)
    d.text((WIDTH - sub_w - 60, 570), sub_text, fill=MUTED_COLOR, font=f_sm)

    img.save(out, "JPEG", quality=85, optimize=True, progressive=True)
    logger.debug(f"OG image generada: {out.name} ({tipo} en {localidad})")
    return out


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _measure(draw, text: str, font) -> int:
    """Pillow ≥10 usa textbbox; el viejo .textsize está deprecado."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def upload_to_wordpress(local_path: Path, wp_client) -> Optional[dict]:
    """Sube la imagen a WP via REST API. Devuelve `{"id": int, "source_url": str}`.

    Cachea por hash del filename dentro del proceso para evitar re-uploads
    cuando la misma imagen se referencia en varios posts.
    """
    if local_path is None or not local_path.exists():
        return None

    cache_key = local_path.stem  # = sha1 de tipo+loc+precio
    if cache_key in _UPLOAD_CACHE:
        return _UPLOAD_CACHE[cache_key]

    try:
        result = wp_client.upload_media(
            local_path=local_path,
            mime_type="image/jpeg",
            title=f"og-{cache_key}",
            alt_text="Vista previa de la subasta",
        )
    except Exception as exc:
        logger.warning(f"OG image upload falló para {local_path.name}: {exc}")
        return None

    if result and result.get("source_url"):
        _UPLOAD_CACHE[cache_key] = result
        return result
    return None


def get_or_create_og_image(
    tipo: str,
    localidad: str,
    precio_str: str,
    provincia: str,
    wp_client,
) -> Tuple[Optional[str], Optional[int]]:
    """Helper one-shot: renderiza + sube + cachea. Devuelve (url, media_id).

    Si cualquier paso falla (Pillow ausente, fonts ausentes, REST falla),
    devuelve (None, None) y el caller debe usar el og:image por defecto.
    """
    local = render_og_image(tipo, localidad, precio_str, provincia)
    if local is None:
        return None, None
    uploaded = upload_to_wordpress(local, wp_client)
    if uploaded is None:
        return None, None
    return uploaded.get("source_url"), uploaded.get("id")
