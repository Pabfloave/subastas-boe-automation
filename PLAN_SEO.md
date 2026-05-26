# Plan de Implementación — Auditoría SEO

> **Documento companion de** [auditoria_seo_tecnico.md](auditoria_seo_tecnico.md)
> **Fecha:** 2026-05-26
> **Branch destino:** `feat/seo-audit-fixes`
> **Tiempo total estimado:** 7-10 días de trabajo efectivo (≈2-3 semanas de calendario)

---

## 0. Decisiones tomadas

| # | Decisión | Implicación |
|---|---|---|
| D1 | **Imagen OG: Pillow local** (sin Google Static Maps) | Genera JPG 1200×630 en Python, sube a `wp-content/uploads/og-cache/{hash}.jpg`. Cero coste, cero tracker. |
| D2 | **Staging: WordPress local en Docker** | Validación local antes de prod. Plantilla `docker-compose.yml` nueva. |
| D3 | **Plugin SEO: Rank Math (solo)** | Limpiamos los `_yoast_wpseo_*` del payload. Reducimos meta fields a la mitad. |

> Si cualquiera de estas tres cambia más adelante, el plan se ajusta puntualmente — no globalmente.

---

## 1. Mapa de dependencias entre acciones

```
 ┌──── Sprint 0 (Entorno) ────┐
 │                             │
 │  Docker WP staging          │
 │  Limpieza Yoast del payload │
 │  Bumpear versión plugin     │
 └────────────┬────────────────┘
              │
 ┌──── Sprint 1 (Quick wins) ──────────────────────┐
 │ A1: Canonical posts       A11: Plugin meta      │
 │ A12: Title truncado       A13: rel=noopener     │
 │ A14: Guardia estado=None  A16: bare except      │
 └────────────┬────────────────────────────────────┘
              │
 ┌──── Sprint 2 (Imagen + Schema + FAQ) ───────────┐
 │ A3: Pillow og:image       A4: <img> static map  │
 │ A8: FAQ unificada         A19: BreadcrumbList   │
 │ (depende A11 para num_lotes)                    │
 └────────────┬────────────────────────────────────┘
              │
 ┌──── Sprint 3 (Performance + Crawl) ─────────────┐
 │ A9: Fonts no bloqueantes  A10: CSS externo      │
 │ A2: SSR + <noscript>      A6: sitemap + ping    │
 └────────────┬────────────────────────────────────┘
              │
 ┌──── Sprint 4 (Long-term) ───────────────────────┐
 │ A7: Contenido único provincias                  │
 │ A5: Archivar templates legacy                   │
 │ A18: Selector provincias top-10 visible         │
 └─────────────────────────────────────────────────┘
```

**Dependencias críticas:**
- A3 (og:image) requiere D1 (Pillow) → añadir `Pillow>=10` a `requirements.txt`.
- A4 (mapa estático) puede ejecutarse en paralelo con A3 si la opción es solo eliminar iframe (sin imagen) — recomendado para evitar acoplamiento.
- A2 (SSR) requiere A11 (`_subasta_num_lotes` en plugin) para mostrar badge correctamente.
- A6 (sitemap) en realidad puede saltarse si Rank Math ya genera `/sitemap_index.xml`. Reducir a "ping post-publish" en `main.py`.

---

## 2. Sprint 0 — Entorno y limpieza (½ día)

### S0.1 Levantar WordPress local en Docker
**Nuevo archivo:** `docker-compose.yml` en raíz del repo.

```yaml
version: "3.8"
services:
  db:
    image: mariadb:11
    environment:
      MYSQL_ROOT_PASSWORD: rootpw
      MYSQL_DATABASE: wp
      MYSQL_USER: wp
      MYSQL_PASSWORD: wp
    volumes: ["./.docker/db:/var/lib/mysql"]
    ports: ["3306:3306"]

  wp:
    image: wordpress:6.4-php8.2-apache
    depends_on: [db]
    environment:
      WORDPRESS_DB_HOST: db:3306
      WORDPRESS_DB_USER: wp
      WORDPRESS_DB_PASSWORD: wp
      WORDPRESS_DB_NAME: wp
      WORDPRESS_DEBUG: "1"
    volumes:
      - ./.docker/wp:/var/www/html
      - ./wordpress/subastas-meta-api.php:/var/www/html/wp-content/plugins/subastas-meta-api/subastas-meta-api.php
    ports: ["8080:80"]
```

**Setup manual (una vez):**
1. `docker compose up -d`
2. Abrir `http://localhost:8080`, completar wizard, instalar Rank Math.
3. Crear application password para `cli.py`.
4. Crear `.env.staging` con `WP_URL=http://localhost:8080`, `WP_USER=admin`, `WP_APP_PASSWORD=…`.
5. `python cli.py --env staging publicar-paginas-provincia` ← validar generación.

**Criterio de aceptación:** publicar 5 subastas de prueba en `localhost:8080`, comprobar que los meta tags de Rank Math se han poblado, ver la página `/subastas-judiciales-sevilla/`.

**Riesgo:** Application Password requiere HTTPS por defecto. En local, añadir filtro en `.docker/wp/wp-config.php`:
```php
add_filter('wp_is_application_passwords_available', '__return_true');
```

---

### S0.2 Limpiar campos Yoast del payload (consecuencia de D3)
**Archivo:** [src/wordpress/publisher.py:1083-1097](src/wordpress/publisher.py:1083) y [src/wordpress/page_generator.py:1076-1092](src/wordpress/page_generator.py:1076)

Eliminar **todas** las claves `_yoast_wpseo_*` del diccionario `meta_fields`. Mantener solo `rank_math_*`. Reduce el payload REST en ~50 % por post.

**Criterio:** los posts publicados no llevan campos Yoast; Rank Math aplica los suyos.

---

### S0.3 Bumpear versión del plugin
**Archivo:** [wordpress/subastas-meta-api.php:5](wordpress/subastas-meta-api.php:5)

```diff
- * Version: 1.0
+ * Version: 1.1
```

Esto facilitará detectar instalaciones desactualizadas en cabecera HTTP `X-Plugin-Version` opcionalmente.

---

## 3. Sprint 1 — Quick wins (1-2 días)

> Cambios puntuales, alto impacto, riesgo mínimo. Se pueden hacer en una sola PR.

### S1.A Acción 1 — Canonical en posts (PR-1)
**Archivo:** [src/wordpress/publisher.py:1043-1097](src/wordpress/publisher.py:1043) — ver diff en informe §3.

**Pasos:**
1. Calcular `canonical_url` a partir de `existing_post["link"]` (si existe) o `make_subasta_slug`.
2. Setear `rank_math_canonical_url` y `rank_math_robots`.

**Validación:**
```bash
python cli.py --env staging publish-single SUB-JA-2025-244895
# luego curl al post:
curl -s http://localhost:8080/?p=NNN | grep canonical
# Esperado: <link rel="canonical" href="http://localhost:8080/subasta-sub-ja-2025-244895/" />
```

---

### S1.B Acción 11 — Plugin expone `_subasta_num_lotes` (PR-1)
**Archivo:** [wordpress/subastas-meta-api.php:11-24](wordpress/subastas-meta-api.php:11) y `:41-54` — ver diff en informe §3.

**Pasos:**
1. Añadir `_subasta_num_lotes` a ambos arrays.
2. Re-empaquetar zip: `cd wordpress && zip -r subastas-meta-api.zip subastas-meta-api.php`.

**Validación:**
```bash
curl -s http://localhost:8080/wp-json/wp/v2/posts/NNN | jq .subasta_meta._subasta_num_lotes
# Esperado: "2"
```

---

### S1.C Acción 12 — Title truncado robusto (PR-1)
**Archivos:** [page_generator.py:183](src/wordpress/page_generator.py:183), [publisher.py:1050-1054](src/wordpress/publisher.py:1050)

Ver diff en informe §3.

**Validación:** verificar que el title de `Castellón` y `Tarragona` ya no exceden 60 chars renderizados.

```python
# tests/test_titles.py
import pytest
from src.wordpress.page_generator import ProvinciaPageGenerator
from config.provinces import PROVINCIAS_ESPANA

@pytest.mark.parametrize("codigo", PROVINCIAS_ESPANA.keys())
def test_title_under_60(codigo, monkeypatch):
    g = ProvinciaPageGenerator()
    html = g.generate_page_content(codigo)
    import re
    title = re.search(r"<title>(.*?)</title>", html).group(1)
    assert len(title) <= 60, f"{codigo}: '{title}' ({len(title)} chars)"
```

---

### S1.D Acción 13 — `rel="noopener noreferrer"` (PR-1)
**Archivo:** [publisher.py](src/wordpress/publisher.py) — 3 ocurrencias.

Diff sencillo: replace global `target="_blank" rel="nofollow"` → `target="_blank" rel="noopener noreferrer nofollow"`.

---

### S1.E Acción 14 — Guardia `estado=None` + bare except (PR-1)
**Archivo:** [publisher.py:474-485](src/wordpress/publisher.py:474) — ver diff en informe §3.

**Validación:** test unitario que crea `Subasta(estado=None)` y verifica que `_generate_content` no crashea.

---

**Criterio de aceptación Sprint 1:**
- PR-1 contiene S1.A-E + S0.2 + S0.3.
- Tests unitarios verdes.
- 1 post de prueba publicado en staging muestra canonical + meta correctos en HTML renderizado.
- Lighthouse SEO ≥ 95 en el post.

---

## 4. Sprint 2 — Imágenes, Schema, FAQ (2-3 días)

### S2.A Acción 3 — Imagen OG con Pillow (PR-2)
**Nuevos archivos:**
- `requirements.txt` → añadir `Pillow>=10.0`
- `src/wordpress/og_image.py` (nuevo)
- `assets/og_template_subasta.jpg` (1200×630 base, opcional)
- `assets/fonts/DMSans-Bold.ttf` (incluir font local)

**`src/wordpress/og_image.py` (≈80 líneas):**
```python
"""
Generador local de imágenes OG (Open Graph) para posts de subastas.
- Sin dependencias externas (no Google Static Maps).
- Cachea por hash determinista en disco.
- Sube a WordPress via REST API y devuelve la URL pública.
"""
from __future__ import annotations
import hashlib
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
from config import settings

CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "og"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
FONT_BOLD = Path(__file__).parent.parent.parent / "assets" / "fonts" / "DMSans-Bold.ttf"
FONT_REGULAR = Path(__file__).parent.parent.parent / "assets" / "fonts" / "DMSans-Regular.ttf"
BG_COLOR = (15, 23, 42)        # color-primary del CSS
ACCENT_COLOR = (217, 119, 6)   # color-accent del CSS
TEXT_COLOR = (255, 255, 255)


def _hash_key(tipo: str, localidad: str, precio: str) -> str:
    raw = f"{tipo}|{localidad}|{precio}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def render_og_image(tipo: str, localidad: str, precio_str: str,
                    provincia: str = "") -> Path:
    """Renderiza una imagen 1200×630 con datos clave y devuelve la ruta local."""
    key = _hash_key(tipo, localidad, precio_str)
    out = CACHE_DIR / f"{key}.jpg"
    if out.exists():
        return out

    img = Image.new("RGB", (1200, 630), BG_COLOR)
    d = ImageDraw.Draw(img)
    f_xl = ImageFont.truetype(str(FONT_BOLD), 72)
    f_lg = ImageFont.truetype(str(FONT_BOLD), 56)
    f_md = ImageFont.truetype(str(FONT_REGULAR), 36)
    f_sm = ImageFont.truetype(str(FONT_REGULAR), 28)

    # Header
    d.text((60, 60), "SUBASTA JUDICIAL", fill=ACCENT_COLOR, font=f_md)
    # Tipo de bien
    d.text((60, 130), tipo.upper(), fill=TEXT_COLOR, font=f_xl)
    # Localidad
    d.text((60, 230), f"en {localidad}", fill=TEXT_COLOR, font=f_lg)
    if provincia and provincia.lower() != localidad.lower():
        d.text((60, 310), provincia, fill=(150, 163, 184), font=f_md)
    # Precio (esquina inferior)
    d.text((60, 480), "VALOR DE SALIDA", fill=ACCENT_COLOR, font=f_sm)
    d.text((60, 520), precio_str, fill=TEXT_COLOR, font=f_lg)
    # Logo / brand (esquina inferior derecha)
    d.text((900, 540), "Comprar en Subasta", fill=TEXT_COLOR, font=f_sm)
    d.text((900, 575), "CAFAVE INVESTMENT", fill=(150, 163, 184), font=f_sm)

    img.save(out, "JPEG", quality=85, optimize=True)
    return out


def upload_to_wordpress(local_path: Path) -> Optional[str]:
    """Sube la imagen a WP via REST media API. Devuelve URL pública o None."""
    import requests
    with open(local_path, "rb") as fh:
        r = requests.post(
            f"{settings.WP_URL}/wp-json/wp/v2/media",
            auth=(settings.WP_USER, settings.WP_APP_PASSWORD),
            headers={
                "Content-Disposition": f'attachment; filename="{local_path.name}"',
                "Content-Type": "image/jpeg",
            },
            data=fh.read(),
            timeout=30,
        )
    if r.status_code in (200, 201):
        return r.json().get("source_url")
    return None
```

**Modificaciones en publisher.py:**
1. Importar `from .og_image import render_og_image, upload_to_wordpress`.
2. En `_generate_schema_markup`, calcular `og_image_url = upload_to_wordpress(render_og_image(...))` UNA vez por post (cachear en `self._og_cache`).
3. Añadir `"image": [og_image_url]` y `"dateModified"` al schema `RealEstateListing` (ver diff en informe §3, Acción 3).
4. Añadir `rank_math_facebook_image` y `rank_math_twitter_image` en `_generate_meta`.
5. Setear `featured_media` (ID del attachment) en `post_data` para que WP lo use como featured image.

**Validación:**
- Generar 3 posts de prueba (vivienda, garaje, finca rústica).
- Verificar imágenes en `.cache/og/` y como attachments en WP.
- Pasar [Open Graph Debugger](https://developers.facebook.com/tools/debug/), [Twitter Card Validator](https://cards-dev.twitter.com/validator) y [Google Rich Results Test](https://search.google.com/test/rich-results).

**Riesgo:** primer publish lento (≈800 ms por imagen). Mitigación: el caché en disco se reutiliza por tipo+localidad+precio (muchas subastas comparten esta tupla → 80 % cache hit).

---

### S2.B Acción 4 — Sustituir iframe Maps por `<img>` (PR-2)
**Archivo:** [publisher.py:854-877](src/wordpress/publisher.py:854)

**Variante adaptada a D1 (sin Google Static Maps):** en lugar de incrustar un mapa, mantener **solo el enlace** a Google Maps + un placeholder SVG ligero con icono y dirección. Suficiente para UX, cero coste, cero JS de terceros.

```diff
                     html += f"""
         <!-- Ubicación (link a Google Maps, sin iframe pesado) -->
         <div class="mapa-ubicacion">
             <h3>📍 Ubicación del Inmueble</h3>
-            <div class="mapa-container">
-                <iframe
-                    src="https://www.google.com/maps?q={direccion_encoded}&output=embed"
-                    width="100%"
-                    height="350"
-                    style="border:0; border-radius: 8px;"
-                    allowfullscreen=""
-                    loading="lazy"
-                    referrerpolicy="no-referrer-when-downgrade">
-                </iframe>
-            </div>
+            <a href="https://www.google.com/maps/search/?api=1&query={direccion_encoded}"
+               target="_blank" rel="noopener noreferrer nofollow"
+               class="mapa-link-card"
+               aria-label="Abrir ubicación en Google Maps">
+              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" aria-hidden="true">
+                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 110-5 2.5 2.5 0 010 5z" fill="#d97706"/>
+              </svg>
+              <div>
+                <strong>{direccion_original}</strong>
+                <span>Pulsa para abrir en Google Maps →</span>
+              </div>
+            </a>
             <p class="mapa-direccion"><strong>Dirección:</strong> {direccion_original}</p>
         </div>
 """
```

**CSS asociado** (añadir al `<style>` de cada post o, idealmente, externalizar — ver S3.B):
```css
.mapa-link-card {
  display: flex; align-items: center; gap: 16px;
  padding: 20px; background: #fffbeb; border-radius: 12px;
  border: 1px solid #fde68a; text-decoration: none; color: #1e293b;
  transition: background .2s;
}
.mapa-link-card:hover { background: #fef3c7; }
.mapa-link-card svg { flex-shrink: 0; }
.mapa-link-card span { display:block; color:#92400e; font-size:.95em; margin-top:4px; }
```

**Validación:**
- Lighthouse Performance: comparar antes/después (esperado: LCP -1.5 s, transferencia -800 KB).
- Confirmar visualmente que el bloque sigue siendo identificable como "ubicación".

---

### S2.C Acción 8 — FAQ con fuente única (PR-2)
**Archivo:** [publisher.py:303-456](src/wordpress/publisher.py:303) — ver diff en informe §3, Acción 8.

**Refactor en 3 pasos:**
1. Extraer `_faq_items(subasta) -> list[tuple[str, str]]`.
2. Reescribir `_generate_faq_schema` para usar `_faq_items`.
3. Reescribir `_generate_faq_html` para usar `_faq_items` (con `<details>/<summary>`).

**Validación:**
- Pasar [Google Rich Results Test](https://search.google.com/test/rich-results) sobre el post.
- Verificar que el número de `<details>` visibles coincide con `mainEntity.length` en el JSON-LD (extraer ambos con `cheerio`/regex).

---

### S2.D Acción 19 — BreadcrumbList con `@id` en último item
**Archivo:** [publisher.py:228-242](src/wordpress/publisher.py:228) — añadir `"item": canonical_url` al último ListItem.

```diff
             breadcrumb_items.append({
                 "@type": "ListItem", "position": 4,
-                "name": f"Subasta {tipo} en {localidad}"
+                "name": f"Subasta {tipo} en {localidad}",
+                "item": canonical_url
             })
```

(Requiere que `canonical_url` se calcule también en `_generate_schema_markup`. Una opción: pasarlo como argumento al método o calcularlo en `publish_subasta` y propagarlo.)

---

**Criterio de aceptación Sprint 2:**
- PR-2 con todos los cambios anteriores.
- 3 posts de prueba en staging pasan Rich Results Test, Twitter Validator y Facebook Debugger.
- Cache OG funciona (`.cache/og/` poblado, segunda generación instantánea).
- Lighthouse mobile: LCP < 2.8 s, CLS < 0.05.

---

## 5. Sprint 3 — Performance + Crawlability (3-5 días)

### S3.A Acción 9 — Fonts no bloqueantes (PR-3)
Ver diff en informe §3, Acción 9. Sustituir además el axis variable por pesos discretos (`wght@400;500;600;700` en lugar de `ital,opsz,wght@0,9..40,…`) — esto reduce el WOFF2 de ≈85 KB a ≈28 KB.

**Validación:** WebPageTest waterfall → ningún render-blocking de fonts.googleapis.com.

---

### S3.B Acción 10 — CSS externo cacheable (PR-3)

**Solución técnica:**
1. Extraer todo el `<style>` de [page_generator.py:268-772](src/wordpress/page_generator.py:268) y [page_generator.py:1287-1532](src/wordpress/page_generator.py:1287) a un único archivo `assets/comprarensubasta.css`.
2. Subirlo a WP via REST `/wp-json/wp/v2/media` o pegarlo en un Custom CSS (Rank Math no afecta a esto). Mejor: subirlo a `wp-content/themes/{tema}/css/` por SFTP/Bedrock.
3. Inline solo lo above-the-fold (≈2 KB de critical CSS: layout grid, hero typography, breadcrumbs).
4. Reemplazar el bloque `<style>` por `<link rel="stylesheet">`.

**Procedimiento:**
```bash
# Extraer CSS
python scripts/extract_css.py > assets/comprarensubasta.css
# Subir a WP
curl -u admin:apppw -X POST http://localhost:8080/wp-json/wp/v2/media \
  -H "Content-Disposition: attachment; filename=comprarensubasta.css" \
  -H "Content-Type: text/css" --data-binary @assets/comprarensubasta.css
```

**Validación:** PageSpeed Insights muestra "Reduce unused CSS" sin la página de provincia entera. Cache HTTP del CSS retornando 304 en segunda visita.

---

### S3.C Acción 2 — SSR de cards + `<noscript>` (PR-4)
**Archivo:** [page_generator.py:870-1050](src/wordpress/page_generator.py:870) — ver diff completo en informe §3, Acción 2.

**Implementación en 4 pasos:**
1. Añadir métodos `_fetch_posts_ssr(slug, limit=20)` y `_render_card_ssr(post)` a la clase `ProvinciaPageGenerator`.
2. En `generate_page_content`, calcular `ssr_cards` antes del return.
3. Sustituir el `<div id="subastas-container">` placeholder por `<div … class="subastas-grid">{ssr_cards}</div>` + `<noscript>`.
4. Modificar el JS para NO resetear el contenedor (cambiar de "asignar nuevo HTML" a `insertAdjacentHTML('beforeend', …)`).

**Caso límite:** primera publicación de una provincia (sin posts aún) → `ssr_cards = ""` y el `<noscript>` muestra "No hay subastas activas". Esto ya es coherente con la rama actual del JS.

**Validación:**
```bash
# Sin JS habilitado (curl ve solo HTML server-rendered)
curl -s http://localhost:8080/subastas-judiciales-sevilla/ | grep -c "subasta-card"
# Esperado: ≥ 20

# Con JS (Puppeteer / Playwright)
npx playwright open http://localhost:8080/subastas-judiciales-sevilla/
# Verificar que se cargan TODOS los posts, sin flicker ni duplicados
```

---

### S3.D Acción 6 — Sitemap ping post-publish (PR-4)

**Asunción:** Rank Math ya genera `https://comprarensubasta.com/sitemap_index.xml`. Lo verificamos en S0.1.

**Si Rank Math NO genera sitemap:** instalar plugin o activar la opción correspondiente. Plan B: implementar `scripts/generate_sitemap.py` (≈80 líneas).

**Si SÍ lo genera:** añadir ping a `main.py` después del bulk publish:

**Nuevo archivo:** `src/wordpress/sitemap_ping.py`
```python
"""Notifica a buscadores tras un bulk publish."""
import logging
import requests
logger = logging.getLogger(__name__)

def ping_search_engines(sitemap_url: str) -> None:
    """Best-effort ping a Google y Bing. Falla silenciosamente."""
    for engine, url in [
        ("Google", f"https://www.google.com/ping?sitemap={sitemap_url}"),
        ("Bing",   f"https://www.bing.com/ping?sitemap={sitemap_url}"),
    ]:
        try:
            r = requests.get(url, timeout=10)
            logger.info(f"Sitemap ping {engine}: HTTP {r.status_code}")
        except Exception as e:
            logger.warning(f"Sitemap ping {engine} failed: {e}")
```

Y en `main.py`, al final de `run_sync()`:
```diff
+    from src.wordpress.sitemap_ping import ping_search_engines
+    ping_search_engines(f"{settings.WP_URL}/sitemap_index.xml")
```

**Validación:** logs muestran `Sitemap ping Google: HTTP 200`.

Y añadir el `<link rel="sitemap">` en `<head>` (ver diff en informe §3, Acción 6).

---

**Criterio de aceptación Sprint 3:**
- PR-3 (perf) + PR-4 (crawl) mergeadas.
- PageSpeed Insights mobile: Performance ≥ 90, SEO 100.
- `curl -s /subastas-judiciales-sevilla/` retorna 20 `subasta-card` HTML.
- Logs de un sync completo muestran ping a buscadores.

---

## 6. Sprint 4 — Contenido + limpieza (continuo)

### S4.A Acción 7 — Textos diferenciados por provincia
**Nuevo archivo:** `config/province_seo_blocks.py`

**Trabajo:** 52 bloques de ~150 palabras cada uno. Distribución:
- **Opción A** — copywriter humano: ~1 día por bloque × 52 ≈ 1 mes.
- **Opción B** — generación con Claude/GPT a partir de plantilla, revisión manual: 2-3 días para los 52.
- **Opción C** — datos abiertos (INE, Ministerio Justicia, Registradores) + plantilla: 1 día.

**Estrategia recomendada (combinación B+C):**
1. Extraer de fuentes abiertas: precio medio m², nº juzgados de 1ª Instancia, principales municipios, % subastas vs. población.
2. Plantilla Jinja2 con esos datos.
3. Pass de copy humano para las 10 provincias top (Madrid, Barcelona, Valencia, Sevilla, Málaga, …) — el long tail puede convivir con texto algo plantilla siempre que tenga datos reales.

**Validación:** Copyscape o `simhash` entre las 52 páginas → similitud < 60 % en el bloque SEO.

---

### S4.B Acción 5 — Archivar templates legacy
**Archivo:** [templates/sevilla_page_raw.html](templates/sevilla_page_raw.html)

```bash
git mv templates/sevilla_page_raw.html templates/_archive/sevilla_demo_pre_2026.html
echo "# Templates" > templates/README.md
echo "" >> templates/README.md
echo "HTML productivo: \`src/wordpress/page_generator.py\`. Esta carpeta solo contiene snapshots históricos para diff visual." >> templates/README.md
```

---

### S4.C Acción 18 — Top-10 provincias visibles
**Archivo:** [page_generator.py:787-847](src/wordpress/page_generator.py:787)

Antes del `<details>` colapsable, mostrar 10 botones directos a las provincias con más subastas (consultar `/wp-json/wp/v2/categories?per_page=10&orderby=count&order=desc`).

```diff
   <nav class="provincia-selector" aria-label="Selector de provincias">
     <h3 class="provincia-selector-title">Subastas por Provincia en España</h3>
+    <div class="provincia-buttons provincia-top">
+      {top10_buttons_html}
+    </div>
     <details>
       <summary style="cursor:pointer;font-weight:500;margin-bottom:10px;">Ver todas las provincias (52)</summary>
```

---

## 7. Pruebas globales y validación

### 7.1 Suite de tests automatizados (a añadir)
**Nuevo archivo:** `tests/test_seo.py` (con `pytest` — añadir a `requirements-dev.txt`).

```python
"""Tests de regresión SEO — corren en CI tras cada cambio."""
import re
import pytest
from src.wordpress.page_generator import ProvinciaPageGenerator
from src.wordpress.publisher import WordPressPublisher
from config.provinces import PROVINCIAS_ESPANA
from tests.fixtures import sample_subasta  # fixture a crear

@pytest.fixture
def page_gen():
    return ProvinciaPageGenerator()

# --- Tests páginas de provincia ---
@pytest.mark.parametrize("codigo", PROVINCIAS_ESPANA.keys())
def test_provincia_has_canonical(codigo, page_gen):
    html = page_gen.generate_page_content(codigo)
    assert re.search(r'<link\s+rel="canonical"\s+href="https://[^"]+"', html)

@pytest.mark.parametrize("codigo", PROVINCIAS_ESPANA.keys())
def test_provincia_has_og_tags(codigo, page_gen):
    html = page_gen.generate_page_content(codigo)
    for prop in ("og:type", "og:url", "og:title", "og:description"):
        assert f'property="{prop}"' in html, f"{codigo} missing {prop}"

@pytest.mark.parametrize("codigo", PROVINCIAS_ESPANA.keys())
def test_provincia_title_under_60(codigo, page_gen):
    html = page_gen.generate_page_content(codigo)
    title = re.search(r"<title>(.*?)</title>", html).group(1)
    assert len(title) <= 60, f"{codigo}: {len(title)} chars"

@pytest.mark.parametrize("codigo", PROVINCIAS_ESPANA.keys())
def test_provincia_has_jsonld(codigo, page_gen):
    html = page_gen.generate_page_content(codigo)
    schemas = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert len(schemas) >= 3, f"{codigo} expected ≥3 JSON-LD blocks, got {len(schemas)}"

@pytest.mark.parametrize("codigo", PROVINCIAS_ESPANA.keys())
def test_provincia_unique_h1(codigo, page_gen):
    html = page_gen.generate_page_content(codigo)
    assert len(re.findall(r"<h1[> ]", html)) == 1

# --- Tests posts de subasta ---
def test_post_canonical_not_empty(sample_subasta):
    pub = WordPressPublisher(client=MockClient())
    meta = pub._generate_meta(sample_subasta)
    assert meta["rank_math_canonical_url"] != ""
    assert meta["rank_math_canonical_url"].startswith("http")

def test_post_faq_count_matches(sample_subasta):
    pub = WordPressPublisher(client=MockClient())
    schema_json = pub._generate_faq_schema(sample_subasta)
    html = pub._generate_faq_html(sample_subasta)
    schema_q_count = schema_json.count('"@type": "Question"')
    html_q_count = html.count("<details") if "<details" in html else html.count("<h3>")
    assert schema_q_count == html_q_count

def test_post_no_iframe(sample_subasta):
    pub = WordPressPublisher(client=MockClient())
    content = pub._generate_content(sample_subasta)
    assert "<iframe" not in content, "Iframes pesados deberían eliminarse"

def test_post_estado_none_doesnt_crash():
    pub = WordPressPublisher(client=MockClient())
    s = sample_subasta_with(estado=None)
    pub._generate_content(s)  # no debe lanzar AttributeError
```

### 7.2 Validadores externos (lista de comprobación)
| Validador | URL | Esperado |
|---|---|---|
| Google Rich Results Test | https://search.google.com/test/rich-results | Pass para FAQPage, BreadcrumbList, RealEstateListing |
| Open Graph Debugger | https://developers.facebook.com/tools/debug/ | og:image presente y válida |
| Twitter Card Validator | https://cards-dev.twitter.com/validator | Card "summary_large_image" |
| Schema.org Validator | https://validator.schema.org/ | 0 errores, 0 warnings críticos |
| W3C HTML Validator | https://validator.w3.org/ | 0 errores estructurales |
| Lighthouse mobile | DevTools | SEO ≥ 95, Perf ≥ 85 |
| PageSpeed Insights | https://pagespeed.web.dev/ | LCP < 2.5 s, CLS < 0.1 |
| GTmetrix waterfall | https://gtmetrix.com/ | < 1 MB transferencia |

### 7.3 Métricas a vigilar post-deploy (semana 1-4)

| Métrica | Herramienta | Pre-deploy | Objetivo |
|---|---|---|---|
| LCP móvil p75 | GSC Core Web Vitals | ≈3.8 s | < 2.5 s |
| Posts indexados | GSC Cobertura | baseline | +30 % en 30 días |
| Rich results FAQ | GSC Mejoras | actual | 100 % elegibles |
| Páginas duplicadas | GSC Cobertura | actual | 0 |
| CTR SERP | GSC Rendimiento | baseline | +15 % long-tail |
| Posiciones promedio | GSC Rendimiento | baseline | +0.5-1 puntos |

---

## 8. Estrategia de roll-out

Como decidiste **Docker WP local** (D2), el roll-out es seguro:

1. **Día 0 (local):** levantar Docker, instalar Rank Math, configurar `.env.staging`.
2. **Días 1-2 (local):** PR-1 (Sprint 0+1). Publicar 20 posts de prueba. Validar con Rich Results Test contra `http://localhost:8080`.
3. **Días 3-5 (local):** PR-2 (Sprint 2). Publicar otros 20. Validar imágenes OG en disco.
4. **Días 6-9 (local):** PR-3 + PR-4 (Sprint 3). Validar Lighthouse + curl sin JS.
5. **Día 10:** code review final. Cherry-pick / merge a `main`.
6. **Día 11 (canary):** ejecutar `cli.py sync` en producción **solo para 1 provincia** (Soria — pocas subastas activas, bajo tráfico). Esperar 24 h.
7. **Día 12-13:** monitor GSC, ratios de errors, tracking de rebote/CTR. Si todo verde → extender a las 52.
8. **Día 14:** activar sitemap ping en `main.py`.
9. **Semana 3-4:** rondas de medición + ajustes finos.

---

## 9. Riesgos y mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|:---:|:---:|---|
| Rank Math overrides nuestros meta tags HTML | Media | Alto | Setear `rank_math_advanced_robots` + verificar render final con `curl`. Plan B: filtrar a Rank Math con `wpseo_canonical` hook en el plugin. |
| Subir imágenes OG inunda `/wp-content/uploads/` | Alta | Medio | Job mensual de limpieza (`scripts/cleanup_og_cache.py`). Cache key determinista evita duplicados. |
| SSR de 20 cards alenta cada publicación | Media | Bajo | Hacer SSR cada N horas con caché de 4 h. Aceptable: `localStorage` revalida en cliente. |
| Lighthouse penaliza CSS aún inline | Baja | Bajo | Sprint 3.B externaliza CSS. Si no se completa, mantenemos baseline actual. |
| Ping a Google/Bing falla en CI | Baja | Mínimo | Try/except + log warning. No bloquea el sync. |
| Posts antiguos con slug histórico tienen canonical diferente al esperado | Alta | Alto | Acción 1 usa `existing_post["link"]` como fuente primaria, slug determinista como fallback. |
| Pillow no encuentra la fuente en CI | Media | Bajo | Fonts vendored en `assets/fonts/`. Tests verifican que `FONT_BOLD.exists()`. |
| Mismatch entre `<details>` (HTML) y `Question` (JSON-LD) tras refactor FAQ | Media | Alto | Test automatizado `test_post_faq_count_matches`. |

---

## 10. Resumen ejecutivo del plan

| Sprint | Días efectivos | Acciones del informe | PRs | Impacto SEO esperado |
|---|:---:|---|---|---|
| **S0** Entorno | 0.5 | Docker WP + limpieza Yoast | PR-0 | Base de desarrollo |
| **S1** Quick wins | 1-2 | 1, 11, 12, 13, 14, 16, 17 | PR-1 | +Canonical, +Title robusto, +Estabilidad |
| **S2** Imágenes + Schema | 2-3 | 3, 4, 8, 19 | PR-2 | +Rich snippets visuales, -1 MB por post |
| **S3** Perf + Crawl | 3-5 | 2, 6, 9, 10 | PR-3, PR-4 | +LCP, +Indexación, +Sitemap |
| **S4** Long-term | continuo | 5, 7, 18 | varios | +Diferenciación, +Click depth |

**Total acciones cubiertas:** 17 de 21 hallazgos (las 4 restantes son cosméticas / ya cubiertas indirectamente).
**Total ficheros tocados:** 8 (publisher.py, page_generator.py, subastas-meta-api.php, main.py, settings, 3 archivos nuevos).
**Nuevas dependencias:** Pillow (>=10), pytest (dev), Docker (dev).

---

**Siguiente acción:** decidir si quieres que arranque por el Sprint 0 (Docker + limpieza Yoast + bumpear plugin) o saltar directamente al Sprint 1 (quick wins) sobre el branch `feat/seo-audit-fixes`.
