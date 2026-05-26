"""IndexNow protocol client (Sprint 3 — Acción 6).

Reemplaza el deprecated `google.com/ping?sitemap=` (Google lo cerró en
junio 2023, Bing en 2022). Notifica a Bing, Yandex, Seznam y Naver de
URLs nuevas o actualizadas en tiempo casi real.

Protocolo: https://www.indexnow.org/documentation

Flujo:
1. Al primer uso se genera una key UUID4 y se persiste en `.cache/indexnow.key`.
2. La key se publica como archivo `<key>.txt` en `/wp-content/uploads/`
   via REST `/wp/v2/media`. En cada POST a IndexNow pasamos
   `keyLocation` apuntando ahí para que Bing valide la propiedad.
3. `notify(urls)` envía un batch de URLs a `bing.com/indexnow`.

Diseño defensivo: cualquier fallo (network, API down, key inválida)
devuelve `False` y deja un warning en log — nunca rompe el sync.
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Iterable, Optional

import requests

logger = logging.getLogger(__name__)

CACHE_ROOT = Path(__file__).resolve().parent.parent.parent / ".cache"
KEY_FILE = CACHE_ROOT / "indexnow.key"
KEY_LOCATION_FILE = CACHE_ROOT / "indexnow.key_location"  # URL pública

# Bing acepta hasta 10.000 URLs por POST.
MAX_URLS_PER_BATCH = 10_000


def _load_or_create_key() -> str:
    """Devuelve la key UUID; la genera y persiste si no existe."""
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    key = uuid.uuid4().hex
    KEY_FILE.write_text(key)
    logger.info(f"IndexNow: nueva key generada → {KEY_FILE}")
    return key


def _load_or_publish_key_location(key: str, wp_client) -> Optional[str]:
    """Sube `<key>.txt` a /wp-content/uploads/ y devuelve la URL pública.

    Si el upload falla o ya hay una URL cacheada, la reutiliza. La URL
    se devuelve a Bing en cada POST via el campo `keyLocation`.
    """
    if KEY_LOCATION_FILE.exists():
        url = KEY_LOCATION_FILE.read_text().strip()
        if url:
            return url

    # Crear archivo .txt local y subirlo via REST media
    txt_path = CACHE_ROOT / f"{key}.txt"
    txt_path.write_text(key)
    try:
        uploaded = wp_client.upload_media(
            local_path=txt_path,
            mime_type="text/plain",
            title=f"IndexNow key {key[:8]}",
        )
    except Exception as exc:
        logger.warning(f"IndexNow: upload de la key falló — {exc}")
        return None

    if not uploaded or not uploaded.get("source_url"):
        logger.warning("IndexNow: WordPress no devolvió source_url al subir la key")
        return None

    url = uploaded["source_url"]
    KEY_LOCATION_FILE.write_text(url)
    logger.info(f"IndexNow: key publicada en {url}")
    return url


def notify(urls: Iterable[str], wp_client, host: str = "comprarensubasta.com") -> bool:
    """Envía un batch de URLs a IndexNow.

    Args:
        urls: URLs absolutas (http o https) del mismo `host`.
        wp_client: WordPressClient (necesario para publicar la key).
        host: dominio sin protocolo.

    Returns:
        True si IndexNow respondió 200/202, False en cualquier otro caso.
        Nunca lanza excepción — pensado para llamarse en el `finally` de
        un sync sin riesgo de romperlo.
    """
    url_list = [u for u in urls if u and u.startswith("http")]
    if not url_list:
        logger.info("IndexNow: sin URLs que notificar")
        return False

    url_list = url_list[:MAX_URLS_PER_BATCH]

    try:
        key = _load_or_create_key()
        key_location = _load_or_publish_key_location(key, wp_client)
    except Exception as exc:
        logger.warning(f"IndexNow: preparación de key falló — {exc}")
        return False

    if not key_location:
        return False

    payload = {
        "host": host,
        "key": key,
        "keyLocation": key_location,
        "urlList": url_list,
    }

    try:
        response = requests.post(
            "https://www.bing.com/indexnow",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning(f"IndexNow: POST falló — {exc}")
        return False

    # IndexNow devuelve 200 = aceptado, 202 = aceptado para procesar.
    # 422 = URLs no válidas para el host (común si hay typos).
    if response.status_code in (200, 202):
        logger.info(f"IndexNow: {len(url_list)} URLs notificadas (HTTP {response.status_code})")
        return True
    logger.warning(
        f"IndexNow: HTTP {response.status_code} — {response.text[:200]}"
    )
    return False


def check_sitemap(wp_url: str) -> bool:
    """Verifica que `wp_url/sitemap_index.xml` responde 200 y es XML.

    Rank Math genera este archivo automáticamente. Si responde 404 o no
    es XML, algo está mal (plugin desactivado, htaccess roto, etc.).
    """
    target = wp_url.rstrip("/") + "/sitemap_index.xml"
    try:
        response = requests.get(target, timeout=10)
    except requests.RequestException as exc:
        logger.warning(f"Sitemap check: GET falló — {exc}")
        return False
    if response.status_code != 200:
        logger.warning(f"Sitemap check: HTTP {response.status_code} en {target}")
        return False
    if "<?xml" not in response.text[:200]:
        logger.warning(f"Sitemap check: {target} no parece XML")
        return False
    logger.info(f"Sitemap check OK: {target}")
    return True
