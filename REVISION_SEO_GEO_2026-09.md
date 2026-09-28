# Revisión SEO, GEO y captación — septiembre 2026

> Sitio: `https://comprarensubasta.com` · Rama: `claude/gallant-hamilton-9uhg3w`
> Complementa a [auditoria_seo_tecnico.md](auditoria_seo_tecnico.md) y [PLAN_SEO.md](PLAN_SEO.md) (Sprints 0-3 ya aplicados).

## 1. Por qué llegan pocos interesados

| # | Causa | Evidencia | Estado |
|---|---|---|---|
| 1 | **Los metadatos SEO de Rank Math nunca se guardaban.** WordPress descarta en silencio las claves `meta` no registradas en REST; el plugin solo registraba `_subasta_*`/`_bien_*`. Títulos, descripciones, canonical, robots e imágenes OG enviados desde Python se perdían. | Google muestra los títulos con la plantilla por defecto: «Subasta Vivienda en Murcia desde 184.725€ - Comprar en Subasta - CAFAVE Investment» y «… \| Inmuebles BOE Actualizado - Pagina para comprar en subastas». | Corregido (plugin 1.5) |
| 2 | **Oferta contradictoria.** Fichas y provincias prometían «análisis gratuito / primera consulta gratuita / asesoramiento legal gratuito»; quien rellena el formulario recibe una propuesta de informe de pago con IBAN. Genera desconfianza y abandono. | `publisher.py`, `page_generator.py`, respuesta automática del plugin. | Corregido en la web (se muestra la oferta real, configurable) |
| 3 | **Errores jurídicos y contradicciones** que restan autoridad (E-E-A-T) y que los motores de IA penalizan: fichas con depósito del 5 % y «20 días hábiles», provincias con «20 % del valor de tasación» como «nuevo régimen», sin explicar el régimen transitorio de la LO 1/2025. | FAQ de fichas y provincias. | Corregido (fuente única `legal_texts.py`) |
| 4 | **Un tercio de las fichas no son subastas judiciales** (AEAT 30 %, recaudación 5 %, notariales 1 %) pero se presentaban como «subasta judicial» con «Juzgado responsable». Además, «comprar un Vivienda» / «Datos del Vivienda». | BD: 1.615 SUB-AT, 267 SUB-RC, 57 notariales de 5.349. | Corregido |
| 5 | **Fichas fuera de su página provincial.** El nombre bilingüe del BOE («Valencia/València», «Alicante/Alacant») no coincidía con la categoría existente y WordPress creaba categorías paralelas con otro slug; esas fichas no aparecían en la página de la provincia. Una categoría «desconocida» (titulada «Araba/Álava») está indexada. | Resultados de Google; lógica de `client.get_or_create_category`. | Corregido para lo nuevo; ejecutar `fix-categories` para lo existente |
| 6 | **Páginas provinciales desactualizadas.** Solo se regeneraban a mano: las fichas pre-renderizadas (SSR) quedaban obsoletas y el JS omitía subastas nuevas. | Ningún workflow regeneraba páginas. | Corregido (regeneración diaria + JS) |
| 7 | **Desperdicio de rastreo e indexación:** cientos de archivos `/category/…/page/117/`, etiquetas por localidad y fichas finalizadas que devuelven 404. | Resultados de Google. | Corregido (301 + noindex) |
| 8 | **CTA solo al final de fichas largas**; en provincias el botón iba a `/contacto/` sin registrar la provincia. | Código. | Corregido |
| 9 | **Entregabilidad del correo sin verificar.** Sin plugin SMTP, WordPress envía con `mail()` y los avisos de WPForms suelen acabar en spam o perderse. | No verificable desde el repositorio. | **Pendiente (manual)** |

## 2. Cambios implementados

**Plugin `wordpress/subastas-meta-api.php` → v1.5** (zip regenerado)
- Registra en REST los campos de Rank Math (`rank_math_title`, `_description`, `_focus_keyword`, `_canonical_url`, `_robots`, `_facebook_image`, `_twitter_image`, `_rich_snippet`) para entradas y páginas.
- 301 de `/category/subastas/{provincia}/` (y paginaciones) a `/subastas-judiciales-{provincia}/`; `desconocida` y `subastas` al índice. Desactivable con `SUBASTAS_REDIRECT_CATEGORY_TO_HUB`.
- 301 de fichas despublicadas (subasta finalizada) a su página provincial en lugar de 404. Desactivable con `SUBASTAS_REDIRECT_EXPIRED`.
- `noindex, follow` en etiquetas y paginaciones de archivo; etiquetas fuera del sitemap.
- El smart tag `{subasta_url}` enlaza a la ficha real (antes, a la portada).

**Fichas (`publisher.py`)**
- Título SEO = título con precio y provincia (≤60 caracteres).
- Tipo de subasta real (judicial, AEAT, recaudación, notarial, administrativa) en descripción, H2, FAQ y bloque de autoridad gestora.
- FAQ con el régimen dual de la LO 1/2025 (depósito art. 669 LEC; pago art. 670.1 LEC), el importe real del anuncio y sin aplicar la LEC a subastas no judiciales.
- Resumen factual de una frase al inicio (lo que citan ChatGPT, Perplexity, AI Overviews).
- CTA intermedio tras la tabla de datos y CTA final con la oferta real (`INFORME_PRECIO`, `INFORME_PLAZO`).
- Bloque y JSON-LD `Person` del abogado responsable con colegiación (art. 10 LSSI; E-E-A-T). Configurable con `AUTOR_NOMBRE`, `AUTOR_COLEGIO`, `AUTOR_COLEGIADO`.
- Categoría provincial con nombre/slug canónicos; provincia deducida del código cuando el BOE no trae el nombre.

**Páginas provinciales e índice (`page_generator.py`)**
- Textos jurídicos corregidos; meta description única ≤160 sin «gratuito»; título de página sin «\| Inmuebles BOE Actualizado».
- Recuento de subastas pre-renderizado y dato fechado citable («A dd/mm/aaaa, nuestro listado recoge N subastas…»).
- CTA al formulario real con la provincia; bloque del abogado responsable y `employee` en el schema.
- JS: sustituye las fichas pre-renderizadas por datos frescos.

**Automatización**
- Nuevo comando `python cli.py paginas` y paso diario en `cleanup.yml` para regenerar las 52 páginas + índice.
- `fix-categories` fusiona categorías duplicadas (mueve las fichas a la canónica).

**Tests:** `tests/test_sprint4.py` (83 casos). Suite completa: 561 tests en verde.

## 3. Despliegue (en este orden)

1. Revisar y fusionar el PR.
2. WordPress → Plugins → subir `wordpress/subastas-meta-api.zip` (v1.5) y activar.
3. `python cli.py fix-categories --dry-run` → revisar la salida → `python cli.py fix-categories`.
4. GitHub Actions → «Actualización Forzada de Subastas» (todas las provincias) para reescribir fichas y metadatos existentes.
5. `python cli.py paginas` (o esperar a la limpieza diaria de las 04:00 UTC).
6. Comprobar en una ficha: `curl -s URL | grep -E '<title>|canonical|og:image'`.

## 4. Pendiente de acción manual (no se puede hacer desde el código)

- **Correo (prioridad máxima):** instalar WP Mail SMTP o FluentSMTP con un buzón del dominio; configurar SPF, DKIM y DMARC en el DNS; enviar una prueba desde WPForms. Comparar el número de filas de *Inversores* (panel de WordPress) con los correos recibidos: si hay más filas que correos, el problema es de entrega, no de tráfico.
- **Rank Math:** Títulos y metas → separador y nombre del sitio; Ajustes → Generales → Título del sitio: «Comprar en Subasta» (hoy aparece «Pagina para comprar en subastas», sin tilde). Local SEO → tipo *LegalService*, nombre, logotipo, dirección y teléfono.
- **Google Search Console y Bing Webmaster Tools:** enviar `sitemap_index.xml`, revisar «Páginas» (duplicadas `-2`, `-8`, `-9` de slugs antiguos) y solicitar retirada de la categoría `desconocida`.
- **GEO / motores de IA:** si el dominio está en Cloudflare, comprobar que «Block AI bots / AI Crawl Control» no bloquea OAI-SearchBot, ChatGPT-User, PerplexityBot, Claude-SearchBot ni Google-Extended; revisar `robots.txt` y `llms.txt`.
- **Aviso legal:** verificar que figuren razón social, NIF, domicilio, datos registrales, colegio profesional y número de colegiado (art. 10 LSSI). Actualizar el «© 2025» del pie.
- **Validar jurídicamente** los textos de `src/wordpress/legal_texts.py` (régimen transitorio de la LO 1/2025) antes de desplegar.
- **Contenido** (plan de `content/seo-plan-2026.md`): publicar la landing del informe jurídico y el artículo de cargas ocultas; son las piezas con mayor intención de contratación.
