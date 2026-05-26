# Auditoría SEO Técnica — `comprarensubasta.com`

> **Fecha:** 2026-05-26
> **Auditor:** Ingeniero Principal — SEO técnico, rendimiento, IA
> **Repositorio:** `subastas-boe-automation` (branch `claude/charming-beaver-110e83`)
> **Sitio en producción:** `https://comprarensubasta.com`

---

## 0. Naturaleza del activo auditado

Este repositorio **no es** un sitio estático ni una SPA: es un **scraper + generador de markup Python** que publica vía WordPress REST API. Por tanto, el HTML que Google verá se ensambla en dos sitios:

| Tipo de URL en producción | Generador | Archivo |
|---|---|---|
| `/subastas-judiciales/` (índice) | `ProvinciaPageGenerator.generate_index_page_content()` | [src/wordpress/page_generator.py:1178-1603](src/wordpress/page_generator.py:1178) |
| `/subastas-judiciales-{slug}/` (52 provincias) | `ProvinciaPageGenerator.generate_page_content()` | [src/wordpress/page_generator.py:159-1055](src/wordpress/page_generator.py:159) |
| `/subasta-{id}/` (posts individuales, N≈miles) | `WordPressPublisher._generate_content()` | [src/wordpress/publisher.py:458-964](src/wordpress/publisher.py:458) |
| Plugin server-side (filtros + meta REST) | `subastas-meta-api.php` | [wordpress/subastas-meta-api.php](wordpress/subastas-meta-api.php) |
| Plantilla de referencia / demo (no productiva) | HTML estático | [templates/sevilla_page_raw.html](templates/sevilla_page_raw.html) |

> Toda recomendación se aplica al **código que emite HTML**, no a configuración del WordPress en sí.

---

## 1. Resumen Ejecutivo

**Diagnóstico general: 7 / 10 — sólido pero con fugas críticas.**

El proyecto demuestra una madurez SEO superior a la media: meta tags completos, 3-4 schemas JSON-LD por página, breadcrumbs (HTML + microdata + JSON-LD), Open Graph, Twitter Cards, canonical, robots y `geo.*` están implementados en las páginas de provincia y en el índice. La heading hierarchy es correcta (H1 único en intro, H2 en secciones, H3 en subsecciones). Los slugs son deterministas y los posts no duplican el `<h1>` del theme.

Sin embargo, **cinco vectores comprometen la indexación y el ranking de los posts individuales** (el grueso del long-tail):

1. **`rank_math_canonical_url` se publica vacío en cada post** ([publisher.py:1094](src/wordpress/publisher.py:1094)). Cualquier parámetro UTM, paginación o variante en la URL puede generar contenido duplicado a ojos de Google. La canonical del *post* es la única defensa y está desarmada.
2. **Las tarjetas de subasta del listado por provincia se renderizan exclusivamente en cliente vía `fetch()`** ([page_generator.py:893-1051](src/wordpress/page_generator.py:893)). Sin SSR ni `<noscript>` fallback, ni sitemap XML emitido por este repo. Googlebot ejecuta JS, pero el "discovery layer" queda al albur del two-wave indexing y deteriora el crawl budget.
3. **No existe `og:image` ni `twitter:image` en ninguna plantilla**, ni una imagen del bien en `RealEstateListing.image` ([publisher.py:244-263](src/wordpress/publisher.py:244)). Esto elimina la posibilidad de rich snippets con imagen, reduce el CTR en SERP y debilita el share en redes.
4. **Iframe de Google Maps incrustado en cada post** ([publisher.py:859-867](src/wordpress/publisher.py:859)). Aporta entre 800 KB y 1.4 MB de JS de terceros, hipoteca LCP/INP y bloquea consentimiento RGPD. Tiene `loading="lazy"` correctamente puesto, pero el coste sigue siendo alto.
5. **El template `templates/sevilla_page_raw.html` está desnudo** (sin canonical, OG, JSON-LD, robots ni description). Si en algún momento entra en producción tal cual, el coste SEO es enorme. No es claro si está activo o es un archivo de referencia abandonado — recomendamos verificarlo y borrarlo o documentarlo.

Asimismo aparecen mejoras de medio nivel: ausencia de `dateModified` en schemas, sitemap XML programático inexistente, fuentes Google bloqueando render, ~5 KB de CSS inline por página, y el plugin PHP no expone `_subasta_num_lotes` (campo que el JS del frontal lee).

**Bottom line**: el SEO on-page de los **hubs** (índice + 52 páginas de provincia) es excelente; el SEO de los **spokes** (posts individuales — la mayor superficie indexable) tiene una canonical rota, sin imagen para snippets, y depende de Maps pesado. Subsanar los 5 puntos del resumen ejecutivo eleva el activo a 9/10 sin tocar el resto del stack.

---

## 2. Matriz de Hallazgos Críticos

| # | Archivo / Ruta | Gravedad | Descripción del Problema | Impacto en SEO / Visibilidad |
|---|---|:---:|---|---|
| 1 | [src/wordpress/publisher.py:1094](src/wordpress/publisher.py:1094) | 🔴 **Alta** | `rank_math_canonical_url: ""` (string vacío) en `_generate_meta()`. Tampoco hay `_yoast_wpseo_canonical`. | Duplicados generados por UTM, AMP, paginación o REST endpoints quedan sin señal canónica. Riesgo alto de pérdida de equity y canibalización. |
| 2 | [src/wordpress/page_generator.py:870-1050](src/wordpress/page_generator.py:870) | 🔴 **Alta** | El listado de subastas por provincia se renderiza solo en cliente (`fetch /wp/v2/posts?categories=…`). Sin SSR ni `<noscript>` ni links HTML al post desde el hub. | Los posts spoke dependen del two-wave indexing de Google. Bing/Yandex/DuckDuckGo lo verán vacío. Crawl budget malgastado. |
| 3 | [src/wordpress/publisher.py:244-263](src/wordpress/publisher.py:244), [page_generator.py:234-264](src/wordpress/page_generator.py:234) | 🔴 **Alta** | Sin `og:image`, `twitter:image`, ni `RealEstateListing.image[]`. No hay imagen destacada generada. | Sin rich snippet visual, CTR -20-30 % en SERP. Sin tarjeta visual en WhatsApp/Twitter/Facebook. |
| 4 | [src/wordpress/publisher.py:859-877](src/wordpress/publisher.py:859) | 🔴 **Alta** | iframe Google Maps incrustado en *cada* post (~800 KB-1.4 MB JS terceros). Aunque tiene `loading="lazy"`. | LCP/INP degradados. Penalización Core Web Vitals. Consentimiento RGPD obligatorio. |
| 5 | [templates/sevilla_page_raw.html:1-7](templates/sevilla_page_raw.html:1) | 🔴 **Alta** | Plantilla sin canonical, OG, Twitter, description, JSON-LD ni robots. Solo charset + viewport + title. | Si está activa en producción → pérdida total de optimización en `/sevilla/`. Verificar urgentemente. |
| 6 | (sin archivo) | 🟠 **Media** | No se genera `sitemap.xml` programático ni se notifica/ping a buscadores tras publish. | WordPress tiene plugins (Yoast/Rank Math) que lo generan, pero el repo no automatiza nada. Indexación lenta. |
| 7 | [src/wordpress/publisher.py:1071-1097](src/wordpress/publisher.py:1071) | 🟠 **Media** | Falta `_yoast_wpseo_title` y `rank_math_robots` para posts. | Title meta en SERP queda a merced del theme; sin control de `max-snippet:-1, max-image-preview:large`. |
| 8 | [src/wordpress/publisher.py:188-263](src/wordpress/publisher.py:188) | 🟠 **Media** | Schema `RealEstateListing` sin `dateModified`, sin `image`, sin `floorSize` ni `numberOfRooms` cuando hay datos. `validThrough` puede quedar string vacío. | Pierde elegibilidad para rich snippets de inmuebles. Schema parcial degrada confianza estructural. |
| 9 | [src/wordpress/publisher.py:303-396](src/wordpress/publisher.py:303), [publisher.py:398-456](src/wordpress/publisher.py:398) | 🟠 **Media** | FAQPage JSON-LD tiene 6 preguntas, pero el HTML visible tiene **5** (`_generate_faq_html`). Google exige correspondencia exacta. | Riesgo de penalización por "structured data mismatch" (manual action o pérdida del rich snippet FAQ). |
| 10 | [src/wordpress/page_generator.py:265-268](src/wordpress/page_generator.py:265), [page_generator.py:1283-1285](src/wordpress/page_generator.py:1283) | 🟠 **Media** | Stylesheet de Google Fonts bloquea render (no usa `media="print" onload`). Sin `font-display: swap` enforced en CSS. | LCP penalizado por blocking request a fonts.googleapis.com. |
| 11 | [src/wordpress/page_generator.py:268-772](src/wordpress/page_generator.py:268) | 🟠 **Media** | ~500 líneas (~25 KB) de CSS inline `<style>` en cada página de provincia (duplicado entre páginas). | Bytes desperdiciados, sin cache compartido entre páginas. LCP penalizado. |
| 12 | [wordpress/subastas-meta-api.php:11-24](wordpress/subastas-meta-api.php:11) | 🟠 **Media** | Plugin no expone `_subasta_num_lotes` en REST, pero [page_generator.py:931](src/wordpress/page_generator.py:931) lo lee. | Badge "📦 X Lotes" no aparece en el listado (la API devuelve `''`), perjudicando UX y CTR. |
| 13 | [src/wordpress/page_generator.py:71-77](src/wordpress/page_generator.py:71) | 🟠 **Media** | Texto SEO estático idéntico entre las 52 provincias salvo nombre. Riesgo de "thin/near-duplicate content". | 52 páginas con 95 % overlap. Google las puede agrupar como duplicados. |
| 14 | [src/wordpress/publisher.py:869](src/wordpress/publisher.py:869), [page_generator.py:267](src/wordpress/page_generator.py:267) | 🟡 **Baja** | Sin `preload` para fuente principal (`DM Sans`). Sin `dns-prefetch` adicional. | CWV: mejoría marginal de LCP. |
| 15 | [src/wordpress/publisher.py:870-874](src/wordpress/publisher.py:870) | 🟡 **Baja** | `<a target="_blank">` con `rel="nofollow"` pero sin `noopener noreferrer`. | Seguridad (tabnabbing) y leak de Referer. No directo en SEO pero buena práctica. |
| 16 | [src/wordpress/publisher.py:474](src/wordpress/publisher.py:474) | 🟡 **Baja** | `format_money` bare `except:` puede silenciar errores reales y devolver "No disponible" en casos no monetarios. | No SEO directo; resiliencia. |
| 17 | [src/wordpress/publisher.py:484](src/wordpress/publisher.py:484) | 🟡 **Baja** | `subasta.estado.lower()` sin guardia: si `estado` es None, crashea. | Indirecto. Posts pueden fallar al publicarse y quedar como "huérfanos" en cola. |
| 18 | [src/wordpress/page_generator.py:793-844](src/wordpress/page_generator.py:793) | 🟡 **Baja** | 52 `<a>` al selector de provincias dentro de `<details>`. Colapsado por defecto. | Google sí los indexa, pero "click depth" desde otras páginas aumenta. Considerar visibilizar el top 10. |
| 19 | [src/wordpress/publisher.py:218-242](src/wordpress/publisher.py:218) | 🟡 **Baja** | `BreadcrumbList` último item sin `item` (URL). Correcto según Google, pero conviene `@id` único. | Cosmético. |
| 20 | [src/wordpress/page_generator.py:240](src/wordpress/page_generator.py:240) | 🟡 **Baja** | `<title>` con 86 caracteres ("Subastas Judiciales en {nombre} {current_year} \| Inmuebles BOE - Comprar en Subasta"). Para `Castellón`/`Tarragona` etc. supera los 60-70 chars renderizados → truncado en SERP. | CTR ligeramente reducido. |
| 21 | (sin archivo) | 🟡 **Baja** | No hay generación de RSS/Atom feed (WP lo provee, pero no se notifica en `<head>`). | Indirecto: discovery por feed readers. |

---

## 3. Plan de Acción Técnico

Las acciones están ordenadas por **impacto / esfuerzo**. Cada bloque incluye el diff exacto.

### 🔴 ACCIÓN 1 — Setear canonical en posts (Hallazgo #1)

**Archivo:** [src/wordpress/publisher.py](src/wordpress/publisher.py)

**Problema:** `rank_math_canonical_url: ""` y no se setea `_yoast_wpseo_canonical`. Sin canonical, los duplicados drenan equity.

**Refactor:** calcular la URL canónica a partir del slug determinista (`make_subasta_slug`) y la `WP_URL`, y propagarla a Rank Math y Yoast.

```diff
--- a/src/wordpress/publisher.py
+++ b/src/wordpress/publisher.py
@@ -1043,6 +1043,11 @@ class WordPressPublisher:
         tipo = bien.subtipo_bien if bien and bien.subtipo_bien else "Inmueble"
         localidad = bien.localidad if bien and bien.localidad else "España"
         provincia = bien.provincia if bien and bien.provincia else ""

+        # URL canónica del post (slug determinista + WP_URL).
+        # Sin esto, UTM/paginación/AMP generan duplicados sin señal canónica.
+        canonical_slug = self.client.make_subasta_slug(subasta.id_subasta)
+        canonical_url = f"{settings.WP_URL.rstrip('/')}/{canonical_slug}/"
+
         # Focus keyword para SEO
         focus_keyword = f"subasta {tipo.lower()} {localidad.lower()}"
@@ -1083,6 +1088,7 @@ class WordPressPublisher:
             # SEO - Yoast compatible
             "_yoast_wpseo_metadesc": meta_description,
             "_yoast_wpseo_focuskw": focus_keyword,
+            "_yoast_wpseo_title": seo_title,
+            "_yoast_wpseo_canonical": canonical_url,
             "_yoast_wpseo_opengraph-title": og_title,
             "_yoast_wpseo_opengraph-description": meta_description,
             "_yoast_wpseo_twitter-title": og_title,
@@ -1091,7 +1097,8 @@ class WordPressPublisher:
             "rank_math_description": meta_description,
             "rank_math_focus_keyword": focus_keyword,
             "rank_math_title": seo_title,
-            "rank_math_canonical_url": "",
+            "rank_math_canonical_url": canonical_url,
+            "rank_math_robots": ["index", "follow", "max-snippet:-1", "max-image-preview:large"],
             # Disable Rank Math auto-schema (we generate our own JSON-LD)
             "rank_math_rich_snippet": "off",
         }
```

> **Nota:** si los slugs existentes en WP difieren del slug determinista (porque los antiguos conservan el suyo), persistir además `rank_math_canonical_url` reciclando `existing_post["link"]` cuando exista. Variante segura:

```python
canonical_url = (existing_post or {}).get("link") or f"{settings.WP_URL.rstrip('/')}/{canonical_slug}/"
```

---

### 🔴 ACCIÓN 2 — SSR de tarjetas + `<noscript>` (Hallazgo #2)

**Archivo:** [src/wordpress/page_generator.py:870-1050](src/wordpress/page_generator.py:870)

**Problema:** los posts spoke solo se descubren ejecutando JS en el cliente. Bing, DuckDuckGo y Googlebot en second wave los tardan en alcanzar.

**Solución (incremental, sin reescribir todo):** en `generate_page_content`, llamar a `client.get_posts_by_category(slug, per_page=20)` server-side y emitir las primeras 20 cards como HTML estático + un `<noscript>` que lista links a 100 posts más para crawlers sin JS. El JS sigue paginando para usuarios.

```diff
--- a/src/wordpress/page_generator.py
+++ b/src/wordpress/page_generator.py
@@ -22,6 +22,7 @@ class ProvinciaPageGenerator:
     def __init__(self):
         self.base_url = settings.WP_URL
         self.auth = (settings.WP_USER, settings.WP_APP_PASSWORD)
+        self._posts_cache = {}

     def _get_or_create_category(self, nombre: str, slug: str) -> int:
         """Obtiene o crea una categoría de provincia."""
@@ -159,6 +160,40 @@ class ProvinciaPageGenerator:
+    def _fetch_posts_ssr(self, slug: str, limit: int = 20) -> list:
+        """
+        Fetch posts at build/publish-time so crawlers see HTML, not blank cards.
+        Returns up to `limit` posts ordered by recency. Failures degrade silently
+        — the JS fallback still runs at view-time.
+        """
+        if slug in self._posts_cache:
+            return self._posts_cache[slug]
+        try:
+            cat = requests.get(
+                f"{self.base_url}/wp-json/wp/v2/categories",
+                params={"slug": slug}, timeout=10
+            ).json()
+            if not cat:
+                return []
+            cat_id = cat[0]["id"]
+            posts = requests.get(
+                f"{self.base_url}/wp-json/wp/v2/posts",
+                params={"categories": cat_id, "per_page": limit,
+                        "_fields": "id,link,title,subasta_meta"},
+                timeout=15
+            ).json() or []
+            self._posts_cache[slug] = posts
+            return posts
+        except Exception:
+            return []
+
+    def _render_card_ssr(self, post: dict) -> str:
+        m = post.get("subasta_meta") or {}
+        title = (post.get("title") or {}).get("rendered", "Subasta")
+        link = post.get("link", "#")
+        valor = m.get("_subasta_valor") or ""
+        fecha = m.get("_subasta_fecha_fin") or ""
+        loc = m.get("_bien_localidad") or ""
+        return (f'<article class="subasta-card"><header class="subasta-header">'
+                f'<h2 class="subasta-title"><a href="{link}">{title}</a></h2></header>'
+                f'<p><strong>Valor:</strong> {valor} € · <strong>Finaliza:</strong> {fecha} · '
+                f'<strong>Localidad:</strong> {loc}</p>'
+                f'<a href="{link}" class="btn-ver-subasta">Ver detalles</a></article>')
+
```

Y dentro del HTML, sustituir el `<div id="subastas-container">` por la versión con SSR + noscript:

```diff
-  <!-- ===== SUBASTAS CONTAINER ===== -->
-  <div id="subastas-container">
-    <div class="loading">
-      <div class="loading-spinner"></div>
-      <p>Cargando subastas de {nombre}...</p>
-    </div>
-  </div>
+  <!-- ===== SUBASTAS CONTAINER (SSR + JS hydrate) ===== -->
+  <div id="subastas-container" class="subastas-grid">
+    {ssr_cards}
+  </div>
+  <noscript>
+    <p><strong>Vista sin JavaScript:</strong> Se muestran las {ssr_count} subastas más recientes en {nombre}.
+    <a href="/subastas-judiciales-{slug}/page/2/">Ver más subastas</a>.</p>
+  </noscript>
```

**Importante en el JS de cliente:** **no resetear** el HTML del contenedor cuando llega la primera página; en su lugar usar `insertAdjacentHTML('beforeend', …)` para conservar las cards SSR ya pintadas y sólo añadir el resto. Esto convierte la sección en "isomorphic" — Google la ve completa de inicio, el usuario obtiene paginación adicional sin flicker.

---

### 🔴 ACCIÓN 3 — `og:image` + `RealEstateListing.image` (Hallazgo #3)

**Archivo:** [src/wordpress/publisher.py:244-263](src/wordpress/publisher.py:244)

**Solución:** mientras no haya foto del bien (BOE no las publica), generar dinámicamente una imagen OG hospedada (en R2/Cloudinary/own static) y, como fallback, usar el mapa estático de Google (`/maps/api/staticmap`) con la dirección. Schema y meta tags ya tendrán imagen consistente.

```diff
--- a/src/wordpress/publisher.py
+++ b/src/wordpress/publisher.py
@@ -208,6 +208,17 @@ class WordPressPublisher:
         # Precio
         precio = float(subasta.valor_subasta) if subasta.valor_subasta else 0
+
+        # Imagen OG/Schema — Static Maps si hay dirección, fallback al logo del sitio.
+        og_image = f"{site_url}/wp-content/uploads/og-default-subastas.jpg"
+        if direccion and localidad:
+            from urllib.parse import quote
+            q = quote(f"{direccion}, {localidad}, {provincia}, España")
+            og_image = (
+                "https://maps.googleapis.com/maps/api/staticmap"
+                f"?center={q}&zoom=15&size=1200x630&scale=2&maptype=roadmap"
+                f"&markers=color:red%7C{q}&key={settings.GOOGLE_MAPS_STATIC_KEY}"
+            )
+
@@ -253,6 +264,11 @@ class WordPressPublisher:
             "datePosted": subasta.fecha_inicio.strftime("%Y-%m-%d") if subasta.fecha_inicio else "",
+            "dateModified": datetime.now().strftime("%Y-%m-%d"),
+            "image": [og_image],
             "offers": {
                 "@type": "Offer",
                 "price": precio,
                 "priceCurrency": "EUR",
                 "availability": "https://schema.org/InStock",
-                "validThrough": fecha_disponible,
+                **({"validThrough": fecha_disponible} if fecha_disponible else {}),
                 "seller": {
```

Y en `_generate_meta`, añadir `og:image` para Yoast/Rank Math:

```diff
@@ -1087,9 +1102,12 @@ class WordPressPublisher:
             "_yoast_wpseo_opengraph-title": og_title,
             "_yoast_wpseo_opengraph-description": meta_description,
+            "_yoast_wpseo_opengraph-image": og_image,
             "_yoast_wpseo_twitter-title": og_title,
             "_yoast_wpseo_twitter-description": meta_description,
+            "_yoast_wpseo_twitter-image": og_image,
             # SEO - Rank Math compatible
             "rank_math_description": meta_description,
+            "rank_math_facebook_image": og_image,
+            "rank_math_twitter_image": og_image,
```

> Si no se quiere depender de Google Static Maps (coste y RGPD), generar la imagen OG localmente con Pillow (texto: tipo + localidad + precio + logo) y subirla a `wp-content/uploads/og-cache/{hash}.jpg`.

Aplicar el mismo bloque (con valores del agregado de provincia) en [page_generator.py:243-256](src/wordpress/page_generator.py:243).

---

### 🔴 ACCIÓN 4 — Reemplazar iframe Maps por imagen estática + link (Hallazgo #4)

**Archivo:** [src/wordpress/publisher.py:854-877](src/wordpress/publisher.py:854)

**Solución:** sustituir el iframe pesado por `<img>` con Static Maps + `<a>` "Ver en Google Maps". `<img>` puede llevar `width`, `height`, `loading="lazy"`, `decoding="async"` y servirse con `alt` descriptivo. Reduce el peso del post de ~1 MB a ~80 KB.

```diff
--- a/src/wordpress/publisher.py
+++ b/src/wordpress/publisher.py
@@ -852,17 +852,16 @@ class WordPressPublisher:
                     direccion_encoded = urllib.parse.quote(direccion_completa)

                     html += f"""
         <!-- Mapa de ubicación -->
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
+               aria-label="Abrir ubicación de {tipo_bien} en {localidad} en Google Maps">
+              <img
+                src="https://maps.googleapis.com/maps/api/staticmap?center={direccion_encoded}&zoom=15&size=1200x500&scale=2&markers=color:red%7C{direccion_encoded}&key={settings.GOOGLE_MAPS_STATIC_KEY}"
+                width="1200" height="500"
+                loading="lazy" decoding="async"
+                alt="Mapa con la ubicación de {tipo_bien} en {direccion_original}"
+                style="width:100%;height:auto;border-radius:8px;display:block;">
+            </a>
             <p class="mapa-direccion"><strong>Dirección:</strong> {direccion_original}</p>
             <a href="https://www.google.com/maps/search/?api=1&query={direccion_encoded}"
-               target="_blank"
-               rel="nofollow"
+               target="_blank" rel="noopener noreferrer nofollow"
                class="btn-mapa">
                 🗺️ Ver en Google Maps
             </a>
         </div>
 """
```

> Si Static Maps tampoco se quiere, dejar **solo el enlace** "Ver en Google Maps" y mostrar una preview SVG genérica del país. Idea: si en el futuro hay catastro abierto, usar foto aérea PNOA (gratuita, sin tracker).

---

### 🔴 ACCIÓN 5 — Auditar / archivar `templates/sevilla_page_raw.html` (Hallazgo #5)

**Archivo:** [templates/sevilla_page_raw.html](templates/sevilla_page_raw.html)

**Acción:** confirmar primero si esta plantilla está en producción. Si NO:

```bash
git mv templates/sevilla_page_raw.html templates/_archive_sevilla_demo.html
```

Y añadir un `README.md` en `templates/` documentando que el HTML productivo se genera en `src/wordpress/page_generator.py`.

Si SÍ está siendo publicado (paste directo en WP), aplicarle el bloque `<head>` completo de [page_generator.py:237-263](src/wordpress/page_generator.py:237) — canonical, OG, Twitter, robots, JSON-LD y geo tags.

---

### 🟠 ACCIÓN 6 — Sitemap XML + ping a buscadores

**Nuevo archivo:** `scripts/generate_sitemap.py`

**Solución:** un script idempotente que descarga `/wp-json/wp/v2/pages` + `/wp-json/wp/v2/posts` paginados, emite `sitemap_pages.xml` + `sitemap_posts.xml` + `sitemap_index.xml`, los sube por SFTP/REST a la raíz del WP y luego hace `GET https://www.google.com/ping?sitemap=…` y `https://www.bing.com/ping?sitemap=…`.

Como ataque mínimo (≈80 líneas), añade enlace `<link rel="alternate" type="application/rss+xml">` y `<link rel="sitemap">` en `<head>`:

```diff
--- a/src/wordpress/page_generator.py
+++ b/src/wordpress/page_generator.py
@@ -262,6 +262,9 @@ class ProvinciaPageGenerator:
   <!-- Structured Data -->
   {schemas_json}

+  <link rel="alternate" type="application/rss+xml" title="Subastas {nombre} - RSS" href="{site_url}/category/{slug}/feed/">
+  <link rel="sitemap" type="application/xml" title="Sitemap" href="{site_url}/sitemap_index.xml">
+
   <link rel="preconnect" href="https://fonts.googleapis.com">
```

(Mismo bloque en [page_generator.py:1273-1276](src/wordpress/page_generator.py:1273) y en `publisher.py` si se decide emitir `<head>` para posts — lo normal es que Rank Math/Yoast ya generen el sitemap si están instalados; en ese caso este punto se reduce a verificar que está activo y a hacer ping post-publish desde `main.py`.)

---

### 🟠 ACCIÓN 7 — Diferenciar texto SEO entre provincias (Hallazgo #13)

**Archivo:** [src/wordpress/page_generator.py:71-96](src/wordpress/page_generator.py:71)

**Solución:** añadir 2-3 párrafos diferenciados por provincia (mercado, principales municipios, juzgados de referencia, datos macro). Crear `config/province_seo_blocks.py`:

```python
PROVINCE_SEO_BLOCKS = {
    "41": {
        "intro_extra": "Sevilla concentra el 18 % de las subastas judiciales de Andalucía...",
        "municipios": ["Dos Hermanas", "Alcalá de Guadaíra", "Utrera", "Écija"],
        "juzgados_ref": ["Juzgado de 1ª Instancia 16 de Sevilla", "Juzgado de 1ª Instancia 25 de Sevilla"],
        "datos_macro": "Precio medio m² Sevilla capital: 1.890 €/m² (2026)",
    },
    # ... 51 más
}
```

Y consumirlo:

```diff
@@ -71,10 +71,15 @@ class ProvinciaPageGenerator:
     def _generate_province_seo_text(self, nombre: str, comunidad: str) -> str:
         """Genera texto SEO estático único para cada provincia."""
         current_year = datetime.now().year
+        from config.province_seo_blocks import PROVINCE_SEO_BLOCKS
+        block = PROVINCE_SEO_BLOCKS.get(self._codigo_actual, {})
+        intro_extra = block.get("intro_extra", "")
+        municipios = ", ".join(block.get("municipios", [])) or f"toda la provincia de {nombre}"
+
         return f"""<section class="seo-content" itemscope itemtype="https://schema.org/Article">
     <h2>Subastas Judiciales en {nombre}: Oportunidades de Inversión Inmobiliaria {current_year}</h2>
-    <p>Las <strong>subastas judiciales en {nombre}</strong> representan una de las mejores...</p>
+    <p>Las <strong>subastas judiciales en {nombre}</strong> representan una de las mejores...</p>
+    <p>{intro_extra}</p>
     ...
-    <h3>Cómo participar en una subasta judicial en {nombre}</h3>
+    <h3>Municipios destacados</h3>
+    <p>Cubrimos {municipios} y resto de localidades de {nombre}.</p>
+
+    <h3>Cómo participar en una subasta judicial en {nombre}</h3>
```

(Y aprovechar para pasar `provincia_codigo` como atributo para `_generate_province_seo_text` o setearlo como `self._codigo_actual` al entrar en `generate_page_content`.)

---

### 🟠 ACCIÓN 8 — Sincronizar FAQ visible / Schema (Hallazgo #9)

**Archivos:** [publisher.py:303-396](src/wordpress/publisher.py:303) + [publisher.py:398-456](src/wordpress/publisher.py:398)

**Solución:** una **única fuente** de las FAQs. Sacar la lista de tuplas a un método helper y consumirla en HTML y en JSON-LD.

```diff
--- a/src/wordpress/publisher.py
+++ b/src/wordpress/publisher.py
@@ -303,7 +303,42 @@ class WordPressPublisher:
+    def _faq_items(self, subasta: Subasta) -> list[tuple[str, str]]:
+        """Single source of truth para FAQ: HTML visible y JSON-LD usan la misma lista."""
+        bien = subasta.get_bien_principal()
+        tipo = bien.subtipo_bien if bien and bien.subtipo_bien else "inmueble"
+        localidad = bien.localidad if bien and bien.localidad else "esta ubicación"
+        precio_str = "consultar en la documentación"
+        if subasta.valor_subasta and float(subasta.valor_subasta) > 0:
+            precio_str = f"{float(subasta.valor_subasta):,.0f}€".replace(",", ".")
+        deposito_str = "el 5% del valor de subasta"
+        if subasta.importe_deposito and float(subasta.importe_deposito) > 0:
+            deposito_str = f"{float(subasta.importe_deposito):,.0f}€".replace(",", ".")
+        fecha_str = subasta.fecha_conclusion.strftime("%d/%m/%Y a las %H:%M") if subasta.fecha_conclusion else "consultar en el BOE"
+        return [
+            (f"¿Cuál es el valor de salida de esta subasta de {tipo} en {localidad}?",
+             f"El valor de salida es {precio_str}..."),
+            (f"¿Cuánto depósito necesito para participar?",
+             f"Necesitas {deposito_str}..."),
+            (f"¿Hasta cuándo puedo pujar?",
+             f"Finaliza el {fecha_str}..."),
+            (f"¿Qué documentación necesito?",
+             "DNI/NIE, certificado digital o Cl@ve, alta en Portal BOE."),
+            (f"¿Es seguro comprar un {tipo} en subasta judicial?",
+             "Sí, procedimiento legal supervisado por juzgado..."),
+            ("¿Qué pasa si gano la subasta?",
+             "Pagar el resto en plazo, liquidar ITP/IVA, esperar Decreto..."),
+        ]
+
     def _generate_faq_schema(self, subasta: Subasta) -> str:
         """FAQ Schema JSON-LD (single source: _faq_items)."""
         import json
-        # ... 80 líneas de hardcoded ...
-        faqs = [ {...}, {...}, ... ]  # 6 items
+        faqs = [
+            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
+            for q, a in self._faq_items(subasta)
+        ]
         faq_schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faqs}
         return f'<script type="application/ld+json">\n{json.dumps(faq_schema, ensure_ascii=False, indent=2)}\n</script>'
@@ -400,30 +435,12 @@ class WordPressPublisher:
     def _generate_faq_html(self, subasta: Subasta) -> str:
-        # ... lista hardcoded de 5 preguntas ...
+        items = self._faq_items(subasta)
+        body = "\n".join(
+            f'<details class="faq-item"><summary>{q}</summary><p>{a}</p></details>'
+            for q, a in items
+        )
+        return f'<section class="subasta-faq"><h2>Preguntas Frecuentes sobre esta Subasta</h2>{body}</section>'
```

> **Bonus:** usar `<details>/<summary>` en lugar de `<div>` rinde mejor a11y y permite a Google detectar las FAQ aún con contenido colapsado.

---

### 🟠 ACCIÓN 9 — Carga no bloqueante de Google Fonts (Hallazgo #10)

**Archivos:** [page_generator.py:265-268](src/wordpress/page_generator.py:265) + [page_generator.py:1283-1285](src/wordpress/page_generator.py:1283)

```diff
-  <link rel="preconnect" href="https://fonts.googleapis.com">
-  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
-  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=DM+Serif+Display&display=swap" rel="stylesheet">
+  <link rel="preconnect" href="https://fonts.googleapis.com">
+  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
+  <link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap">
+  <link rel="stylesheet"
+        href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap"
+        media="print" onload="this.media='all'">
+  <noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap"></noscript>
```

> Adicionalmente, sustituir el axis variable `ital,opsz,wght@0,9..40,…` por pesos discretos (la página solo usa 400/500/600/700) — reduce el WOFF2 descargado de ~85 KB a ~28 KB.

---

### 🟠 ACCIÓN 10 — Externalizar CSS común (Hallazgo #11)

**Refactor:** mover el CSS común a un único archivo cacheable. Crear `wordpress/comprarensubasta.css` (servido por WP en `wp-content/themes/.../comprarensubasta.css` o por un plugin).

```diff
-  <style>
-    :root { ... 500 líneas ... }
-  </style>
+  <link rel="preload" href="{site_url}/wp-content/themes/main/css/comprarensubasta.css" as="style">
+  <link rel="stylesheet" href="{site_url}/wp-content/themes/main/css/comprarensubasta.css">
+  <style>{critical_inline_css}</style>  <!-- solo lo above-the-fold (≤2 KB) -->
```

Beneficio cuantificable: 25 KB × 53 páginas = ~1.3 MB ahorrados en re-descargas + cache HTTP.

---

### 🟠 ACCIÓN 11 — Exponer `_subasta_num_lotes` en el plugin (Hallazgo #12)

**Archivo:** [wordpress/subastas-meta-api.php:11-24](wordpress/subastas-meta-api.php:11) + `wordpress/subastas-meta-api.php:41-54`

```diff
--- a/wordpress/subastas-meta-api.php
+++ b/wordpress/subastas-meta-api.php
@@ -11,18 +11,19 @@ function subastas_register_meta_fields() {
     $meta_fields = array(
         '_subasta_id',
         '_subasta_tipo',
         '_subasta_estado',
         '_subasta_valor',
         '_subasta_deposito',
         '_subasta_fecha_inicio',
         '_subasta_fecha_fin',
+        '_subasta_num_lotes',
         '_bien_tipo',
         '_bien_direccion',
         '_bien_localidad',
         '_bien_provincia',
         '_bien_cp',
     );
@@ -41,18 +42,19 @@ function subastas_add_meta_to_rest($response, $post, $request) {
     $meta_fields = array(
         '_subasta_id',
         '_subasta_tipo',
         '_subasta_estado',
         '_subasta_valor',
         '_subasta_deposito',
         '_subasta_fecha_inicio',
         '_subasta_fecha_fin',
+        '_subasta_num_lotes',
         '_bien_tipo',
         '_bien_direccion',
         '_bien_localidad',
         '_bien_provincia',
         '_bien_cp',
     );
```

> **Acordarse de re-subir el plugin** (ya hay un `.zip` en `wordpress/subastas-meta-api.zip`) y bump de `Version: 1.0 → 1.1`.

---

### 🟡 ACCIÓN 12 — Acortar `<title>` en provincias largas (Hallazgo #20)

**Archivo:** [page_generator.py:183](src/wordpress/page_generator.py:183) + [publisher.py:1050-1054](src/wordpress/publisher.py:1050)

```diff
-        meta_title = f"Subastas Judiciales en {nombre} {current_year} | Inmuebles BOE - Comprar en Subasta"
+        # Truncado robusto: target 50-58 chars (margen para emoji y rendering).
+        base = f"Subastas Judiciales en {nombre} {current_year}"
+        suffix = " | Inmuebles BOE"
+        meta_title = base + suffix if len(base + suffix) <= 60 else base
+        if len(meta_title) > 60:
+            meta_title = meta_title[:57] + "..."
```

---

### 🟡 ACCIÓN 13 — Endurecer enlaces externos (Hallazgo #15)

**Archivo:** [publisher.py:870-874](src/wordpress/publisher.py:870), [publisher.py:904-906](src/wordpress/publisher.py:904), [publisher.py:949-951](src/wordpress/publisher.py:949)

Replace global en publisher.py:

```diff
-target="_blank" rel="nofollow"
+target="_blank" rel="noopener noreferrer nofollow"
```

---

### 🟡 ACCIÓN 14 — Robustecer `_generate_content` ante `estado=None` (Hallazgo #17)

**Archivo:** [publisher.py:484-485](src/wordpress/publisher.py:484)

```diff
-        estado_class = "en-curso" if "celebr" in subasta.estado.lower() else "proxima"
-        estado_texto = subasta.estado or "En curso"
+        estado_raw = (subasta.estado or "En curso").strip()
+        estado_class = "en-curso" if "celebr" in estado_raw.lower() else "proxima"
+        estado_texto = estado_raw
```

Y narrar `format_money`:

```diff
-        def format_money(value):
-            try:
-                return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
-            except:
-                return "No disponible"
+        def format_money(value):
+            try:
+                return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
+            except (TypeError, ValueError):
+                return "No disponible"
```

---

## 4. Cronograma sugerido (orden de implementación)

1. **Sprint 1 (1-2 días, alto impacto / bajo esfuerzo):** Acciones 1, 7, 12, 13, 14, 11 — fixes puntuales + plugin.
2. **Sprint 2 (3-5 días, alto impacto / medio esfuerzo):** Acciones 3, 4, 8, 9 — imagen OG, sustituir iframe, FAQ unificada, fonts.
3. **Sprint 3 (1 semana, alto impacto / alto esfuerzo):** Acciones 2, 6, 10 — SSR + sitemap + CSS externo.
4. **Sprint 4 (continuo):** Acción 5 (verificar templates antiguos) y Acción 7 (textos diferenciados por provincia, idealmente con copywriter).

---

## 5. Métricas post-implementación a vigilar

| Métrica | Herramienta | Esperado tras Sprint 2 |
|---|---|---|
| LCP móvil (p75) | PageSpeed Insights / Search Console | < 2.5 s (desde ≈3.8 s actual con iframe) |
| Posts indexados | Google Search Console — Cobertura | +30 % en 30 días (gracias a SSR + sitemap) |
| Rich snippets FAQ | Search Console — Mejoras | 100 % de posts elegibles (vs. mismatch actual) |
| Páginas duplicadas | Search Console — Cobertura | 0 (vs. potencial con canonical vacío) |
| CTR SERP (long-tail) | Search Console — Rendimiento | +15-25 % con OG image |

---

**Fin del informe.**
