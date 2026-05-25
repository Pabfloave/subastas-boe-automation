"""
Generador de páginas de subastas por provincia para WordPress.
Crea páginas dinámicas que cargan subastas desde la API REST.
Soporta las 52 provincias de España.
SEO optimizado: meta tags, Open Graph, JSON-LD, contenido estático indexable.
"""
import json
import sqlite3
import requests
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from config import settings
from config.provinces import PROVINCIAS_ESPANA

# Cache de IDs de categorías (se llena dinámicamente)
_CATEGORIA_CACHE = {}

# Nombres cortos para títulos SEO (<60 chars) cuando el oficial es muy largo
PROVINCE_SHORT_NAME = {
    "Santa Cruz de Tenerife": "S.C. Tenerife",
}

# ITP (Impuesto Transmisiones Patrimoniales) - tipo general por CCAA
# para adjudicaciones de inmuebles en subasta. Algunas CCAA tienen
# tipos reducidos para vivienda habitual; mostramos el tipo general.
ITP_POR_CCAA = {
    "Andalucía": "7%",
    "Aragón": "8% (hasta 400.000€) - 8,5%/9%/10% en tramos superiores",
    "Principado de Asturias": "8% (hasta 300.000€) - 9%/10% en tramos superiores",
    "Islas Baleares": "8% (hasta 400.000€) - escalado hasta 13% en tramos superiores",
    "Canarias": "6,5%",
    "Cantabria": "9% (con tipos reducidos del 5%-7% para vivienda habitual)",
    "Castilla-La Mancha": "9% (con bonificaciones para vivienda habitual)",
    "Castilla y León": "8% (hasta 250.000€) - 10% en tramos superiores",
    "Cataluña": "10% (hasta 1.000.000€) - 11% en tramos superiores",
    "Comunidad de Madrid": "6%",
    "Comunidad Valenciana": "10%",
    "Extremadura": "8% (hasta 350.000€) - 10%/11% en tramos superiores",
    "Galicia": "10% (8% para vivienda habitual hasta 150.000€)",
    "La Rioja": "7%",
    "Navarra": "6% (4% vivienda habitual hasta 180.304€)",
    "Comunidad Foral de Navarra": "6% (4% vivienda habitual hasta 180.304€)",
    "País Vasco": "4% (régimen foral - 2,5% vivienda habitual)",
    "Región de Murcia": "8%",
    "Ciudad Autónoma": "IPSI 0,5% (Ceuta/Melilla, sin ITP general)",
}


class ProvinciaPageGenerator:
    """Genera páginas de provincia para WordPress."""

    def __init__(self):
        self.base_url = settings.WP_URL
        self.auth = (settings.WP_USER, settings.WP_APP_PASSWORD)

    def _get_or_create_category(self, nombre: str, slug: str) -> int:
        """Obtiene o crea una categoría de provincia."""
        global _CATEGORIA_CACHE

        if slug in _CATEGORIA_CACHE:
            return _CATEGORIA_CACHE[slug]

        # Buscar categoría existente
        response = requests.get(
            f"{self.base_url}/wp-json/wp/v2/categories",
            params={"slug": slug}
        )
        if response.status_code == 200:
            cats = response.json()
            if cats:
                _CATEGORIA_CACHE[slug] = cats[0]["id"]
                return cats[0]["id"]

        # Buscar categoría padre "Subastas"
        response = requests.get(
            f"{self.base_url}/wp-json/wp/v2/categories",
            params={"slug": "subastas"}
        )
        parent_id = 0
        if response.status_code == 200:
            cats = response.json()
            if cats:
                parent_id = cats[0]["id"]

        # Crear nueva categoría
        response = requests.post(
            f"{self.base_url}/wp-json/wp/v2/categories",
            auth=self.auth,
            json={
                "name": nombre,
                "slug": slug,
                "parent": parent_id
            }
        )
        if response.status_code in (200, 201):
            cat_id = response.json()["id"]
            _CATEGORIA_CACHE[slug] = cat_id
            return cat_id

        return 0

    def _get_provincia_stats(self, provincia_codigo: str) -> dict:
        """
        Consulta la BD para obtener datos dinámicos del FAQ:
        - total_activas: número de subastas activas en la provincia
        - juzgados: top 5 autoridades gestoras (lista de (nombre, count))
        - proximas: próximas 5 subastas (lista de (fecha_iso, subtipo, localidad))

        Devuelve defaults seguros si la BD no está disponible o no tiene datos
        (las respuestas del FAQ usan fallbacks estáticos en ese caso).
        """
        stats = {"total_activas": 0, "juzgados": [], "proximas": []}
        try:
            conn = sqlite3.connect(settings.DB_PATH)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT COUNT(DISTINCT s.id_subasta)
                FROM subastas s
                JOIN bienes b ON s.id_subasta = b.id_subasta
                WHERE b.provincia_codigo = ? AND s.activa = 1
                """,
                (provincia_codigo,),
            )
            row = cursor.fetchone()
            stats["total_activas"] = (row[0] if row else 0) or 0

            cursor.execute(
                """
                SELECT s.autoridad_gestora, COUNT(DISTINCT s.id_subasta) AS cnt
                FROM subastas s
                JOIN bienes b ON s.id_subasta = b.id_subasta
                WHERE b.provincia_codigo = ? AND s.activa = 1
                  AND s.autoridad_gestora IS NOT NULL AND s.autoridad_gestora != ''
                GROUP BY s.autoridad_gestora
                ORDER BY cnt DESC
                LIMIT 5
                """,
                (provincia_codigo,),
            )
            stats["juzgados"] = [(r[0], r[1]) for r in cursor.fetchall()]

            cursor.execute(
                """
                SELECT s.fecha_conclusion, b.subtipo_bien, b.localidad
                FROM subastas s
                JOIN bienes b ON s.id_subasta = b.id_subasta
                WHERE b.provincia_codigo = ? AND s.activa = 1
                  AND s.fecha_conclusion > datetime('now')
                GROUP BY s.id_subasta
                ORDER BY s.fecha_conclusion ASC
                LIMIT 5
                """,
                (provincia_codigo,),
            )
            stats["proximas"] = [(r[0], r[1], r[2]) for r in cursor.fetchall()]

            conn.close()
        except sqlite3.Error:
            pass
        return stats

    @staticmethod
    def _build_meta_title(nombre: str, year: int, total_activas: int) -> str:
        """Construye el <title> SEO con el formato '{Prov} {year} | {N} activos BOE actualizados'.

        Aplica nombre corto para provincias con nombre largo y trunca de forma
        progresiva si supera los 60 caracteres recomendados por Google.
        """
        nombre_corto = PROVINCE_SHORT_NAME.get(nombre, nombre)
        if total_activas > 0:
            full = (
                f"Subastas Judiciales {nombre_corto} {year} | "
                f"{total_activas} activos BOE actualizados"
            )
            if len(full) <= 60:
                return full
            shorter = (
                f"Subastas Judiciales {nombre_corto} {year} | "
                f"{total_activas} activos BOE"
            )
            if len(shorter) <= 60:
                return shorter
            return shorter[:60]
        full = f"Subastas Judiciales {nombre_corto} {year} | Inmuebles BOE actualizados"
        return full if len(full) <= 60 else f"Subastas Judiciales {nombre_corto} {year} | BOE"

    def _generate_province_seo_text(self, nombre: str, comunidad: str) -> str:
        """Genera texto SEO estático único para cada provincia."""
        current_year = datetime.now(timezone.utc).year
        return f"""<section class="seo-content" itemscope itemtype="https://schema.org/Article">
    <h2>Subastas Judiciales en {nombre}: Oportunidades de Inversi\u00f3n Inmobiliaria {current_year}</h2>
    <p>Las <strong>subastas judiciales en {nombre}</strong> representan una de las mejores v\u00edas para adquirir inmuebles por debajo de su valor de mercado. A trav\u00e9s del <strong>Portal de Subastas del BOE</strong>, puede acceder a viviendas, locales comerciales, garajes y fincas r\u00fasticas embargadas en la provincia de {nombre} ({comunidad}) con descuentos que pueden alcanzar entre el 30% y el 60% sobre el precio de tasaci\u00f3n.</p>
    <p>En CAFAVE INVESTMENT actualizamos diariamente todas las subastas publicadas en el Bolet\u00edn Oficial del Estado para {nombre}, ofreciendo informaci\u00f3n verificada sobre valores de subasta, dep\u00f3sitos necesarios, fechas de finalizaci\u00f3n y estado de cada procedimiento. Nuestro equipo de abogados especializados analiza las cargas registrales y la situaci\u00f3n posesoria de cada inmueble antes de recomendar una inversi\u00f3n.</p>

    <h3>Tipos de inmuebles disponibles en subastas en {nombre}</h3>
    <ul>
      <li><strong>Viviendas y pisos</strong> \u2013 Apartamentos, \u00e1ticos, chalets y d\u00faplex embargados</li>
      <li><strong>Locales comerciales</strong> \u2013 Locales en zonas prime para negocio o inversi\u00f3n</li>
      <li><strong>Garajes y trasteros</strong> \u2013 Plazas de aparcamiento a precios reducidos</li>
      <li><strong>Naves industriales</strong> \u2013 Espacios industriales y log\u00edsticos</li>
      <li><strong>Fincas r\u00fasticas y solares</strong> \u2013 Terrenos para edificar o explotaci\u00f3n agr\u00edcola</li>
    </ul>

    <h3>C\u00f3mo participar en una subasta judicial en {nombre}</h3>
    <ol>
      <li><strong>Identifique la subasta</strong> \u2013 Consulte nuestro listado actualizado de subastas activas en {nombre}.</li>
      <li><strong>Analice la documentaci\u00f3n</strong> \u2013 Revise el edicto, las cargas registrales y la situaci\u00f3n posesoria. <em>Le recomendamos asesoramiento profesional.</em></li>
      <li><strong>Deposite la garant\u00eda</strong> \u2013 Ingrese el 20% del valor de tasaci\u00f3n en el Portal de Subastas del BOE.</li>
      <li><strong>Realice su puja</strong> \u2013 Las subastas electr\u00f3nicas est\u00e1n abiertas durante 20 d\u00edas naturales.</li>
      <li><strong>Adjudicaci\u00f3n</strong> \u2013 Si resulta adjudicatario, complete el pago y proceda a la escrituraci\u00f3n.</li>
    </ol>
  </section>"""

    def _generate_faq_section(self, nombre: str, comunidad: str, stats: dict) -> Tuple[str, dict]:
        """Genera sección FAQ con Schema markup FAQPage para rich snippets.

        Pattern de 5 preguntas:
          1. Cuántas subastas activas (dinámico)
          2. Qué juzgados gestionan (dinámico, fallback estático si DB vacía)
          3. ITP por CCAA (estático por comunidad)
          4. Próximas subastas (dinámico, fallback estático si DB vacía)
          5. Necesito abogado (estático con CTA al informe jurídico)
        """
        total = stats.get("total_activas", 0)
        juzgados = stats.get("juzgados", [])
        proximas = stats.get("proximas", [])
        itp = ITP_POR_CCAA.get(comunidad, "consultar normativa autonómica vigente")

        if total > 0:
            q1_a = (
                f"Actualmente hay <strong>{total} subastas judiciales activas en {nombre}</strong> "
                f"publicadas en el Portal de Subastas del BOE. Este listado se actualiza diariamente "
                f"con los nuevos procedimientos del Boletín Oficial del Estado. Puede consultar el "
                f"listado completo en la parte superior de esta página."
            )
        else:
            q1_a = (
                f"El número de subastas judiciales activas en {nombre} varía cada día. "
                f"Consulte el listado actualizado en la parte superior de esta página, "
                f"sincronizado con el BOE cada 24 horas."
            )

        if juzgados:
            items = "; ".join(f"{j[0]} ({j[1]} subastas)" for j in juzgados)
            q2_a = (
                f"En {nombre} las subastas judiciales son gestionadas principalmente por los siguientes "
                f"juzgados: {items}. Cada subasta indica el juzgado responsable y el número de "
                f"procedimiento en su ficha individual."
            )
        else:
            q2_a = (
                f"En {nombre}, las subastas judiciales civiles las tramitan los <strong>Juzgados de "
                f"Primera Instancia e Instrucción</strong> del partido judicial correspondiente. Las "
                f"subastas concursales corresponden al <strong>Juzgado de lo Mercantil</strong>. Cada "
                f"anuncio del BOE identifica el juzgado y el número de procedimiento; consulte la ficha "
                f"individual de cada subasta para conocer el juzgado competente."
            )

        q3_a = (
            f"En {nombre} ({comunidad}) el <strong>Impuesto sobre Transmisiones Patrimoniales (ITP)</strong> "
            f"aplicable a la adjudicación de inmuebles en subasta judicial es: <strong>{itp}</strong>. "
            f"El ITP se devenga al adjudicarse el bien y se calcula sobre el precio de adjudicación "
            f"(no sobre el valor de tasación). Algunas CCAA aplican tipos reducidos para vivienda "
            f"habitual o jóvenes; conviene sumarlo al presupuesto de la inversión."
        )

        if proximas:
            items_html = "<ul>"
            for fecha_iso, subtipo, localidad in proximas:
                try:
                    fecha = datetime.fromisoformat(fecha_iso)
                    fecha_fmt = fecha.strftime("%d/%m/%Y %H:%M")
                except (ValueError, TypeError):
                    fecha_fmt = fecha_iso or "Fecha por confirmar"
                tipo = subtipo or "Inmueble"
                loc = localidad or nombre
                items_html += f"<li><strong>{fecha_fmt}</strong> — {tipo} en {loc}</li>"
            items_html += "</ul>"
            q4_a = (
                f"Las próximas subastas que finalizan en {nombre} son: {items_html} "
                f"Las subastas electrónicas del BOE duran 20 días naturales. Consulte el listado "
                f"completo en la parte superior para más detalles."
            )
        else:
            q4_a = (
                f"Las subastas judiciales en {nombre} se publican y finalizan continuamente en el "
                f"Portal de Subastas del BOE. Cada subasta electrónica permanece abierta durante "
                f"20 días naturales. Consulte el listado actualizado en la parte superior de esta "
                f"página para conocer las fechas de finalización de las subastas activas."
            )

        q5_a = (
            f"No es legalmente obligatorio contar con abogado para pujar como particular en una "
            f"subasta judicial en {nombre}, pero es <strong>muy recomendable</strong> realizar un "
            f"análisis previo del expediente: cargas registrales, situación posesoria del inmueble, "
            f"deudas con la comunidad de propietarios, derechos de tanteo y retracto, y la viabilidad "
            f"jurídica de la adjudicación. Puede solicitar nuestro "
            f'<a href="/informe-juridico-subasta/">informe jurídico de subasta</a> para un análisis '
            f"profesional antes de pujar."
        )

        faqs = [
            {"q": f"¿Cuántas subastas judiciales hay activas en {nombre}?", "a": q1_a},
            {"q": f"¿Qué juzgados gestionan las subastas en {nombre}?", "a": q2_a},
            {"q": f"¿Cuál es el ITP en {nombre} para inmuebles adjudicados en subasta?", "a": q3_a},
            {"q": f"¿Cuándo se celebran las próximas subastas en {nombre}?", "a": q4_a},
            {"q": f"¿Necesito un abogado para participar en subasta en {nombre}?", "a": q5_a},
        ]

        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": faq["q"],
                    "acceptedAnswer": {"@type": "Answer", "text": faq["a"]},
                }
                for faq in faqs
            ],
        }

        faq_html = '<section class="faq-section" itemscope itemtype="https://schema.org/FAQPage">\n'
        faq_html += f'    <h2>Preguntas Frecuentes sobre Subastas Judiciales en {nombre}</h2>\n'
        for faq in faqs:
            faq_html += f'''    <div class="faq-item-wrapper" itemprop="mainEntity" itemscope itemtype="https://schema.org/Question">
      <details class="faq-item">
        <summary itemprop="name">{faq["q"]}</summary>
        <div class="faq-answer" itemprop="acceptedAnswer" itemscope itemtype="https://schema.org/Answer">
          <div itemprop="text">{faq["a"]}</div>
        </div>
      </details>
    </div>
'''
        faq_html += '  </section>'

        return faq_html, faq_schema

    def generate_page_content(self, provincia_codigo: str, stats: Optional[dict] = None) -> str:
        """
        Genera el contenido HTML completo para una página de provincia.
        Optimizado para SEO: meta tags, Open Graph, JSON-LD, contenido estático indexable.

        Acepta `stats` opcional para evitar un segundo SELECT a la BD cuando
        `create_page` ya las consultó.
        """
        prov = PROVINCIAS_ESPANA.get(provincia_codigo)
        if not prov:
            raise ValueError(f"Código de provincia no válido: {provincia_codigo}")

        nombre = prov["nombre"]
        slug = prov["slug"]
        comunidad = prov.get("comunidad", "España")
        current_year = datetime.now(timezone.utc).year
        page_url = f"https://comprarensubasta.com/subastas-judiciales-{slug}/"
        site_url = "https://comprarensubasta.com"

        if stats is None:
            stats = self._get_provincia_stats(provincia_codigo)
        total_activas = stats.get("total_activas", 0)

        meta_description = (
            f"Subastas judiciales en {nombre} {current_year}. "
            f"Listado actualizado de pisos, casas, locales y fincas embargadas en {nombre} ({comunidad}). "
            f"Descuentos del 30-60%. Asesoramiento legal gratuito."
        )
        if len(meta_description) > 160:
            meta_description = meta_description[:157] + "..."

        meta_title = self._build_meta_title(nombre, current_year, total_activas)

        # JSON-LD structured data
        breadcrumb_schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Inicio", "item": site_url},
                {"@type": "ListItem", "position": 2, "name": "Subastas Judiciales", "item": f"{site_url}/subastas-judiciales/"},
                {"@type": "ListItem", "position": 3, "name": f"Subastas en {nombre}", "item": page_url}
            ]
        }

        webpage_schema = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": meta_title,
            "description": meta_description,
            "url": page_url,
            "isPartOf": {"@type": "WebSite", "name": "Comprar en Subasta", "url": site_url},
            "about": {
                "@type": "Service",
                "name": f"Subastas Judiciales en {nombre}",
                "serviceType": "Venta de inmuebles en subasta judicial",
                "areaServed": {
                    "@type": "AdministrativeArea",
                    "name": nombre,
                    "containedInPlace": {"@type": "Country", "name": "España"}
                }
            },
            "provider": {
                "@type": "LegalService",
                "name": "CAFAVE INVESTMENT",
                "url": site_url,
                "areaServed": {"@type": "Country", "name": "España"}
            },
            "inLanguage": "es",
            "dateModified": datetime.now(timezone.utc).strftime("%Y-%m-%d")
        }

        # Generate FAQ section and schema
        faq_html, faq_schema = self._generate_faq_section(nombre, comunidad, stats)
        seo_text = self._generate_province_seo_text(nombre, comunidad)

        # Combine all schemas
        schemas_json = (
            f'<script type="application/ld+json">\n{json.dumps(breadcrumb_schema, ensure_ascii=False, indent=2)}\n</script>\n'
            f'<script type="application/ld+json">\n{json.dumps(webpage_schema, ensure_ascii=False, indent=2)}\n</script>\n'
            f'<script type="application/ld+json">\n{json.dumps(faq_schema, ensure_ascii=False, indent=2)}\n</script>'
        )

        return f'''<!-- wp:html -->
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{meta_title}</title>
  <meta name="description" content="{meta_description}">
  <link rel="canonical" href="{page_url}">

  <!-- Open Graph / Facebook -->
  <meta property="og:type" content="website">
  <meta property="og:url" content="{page_url}">
  <meta property="og:title" content="{meta_title}">
  <meta property="og:description" content="{meta_description}">
  <meta property="og:site_name" content="Comprar en Subasta - CAFAVE INVESTMENT">
  <meta property="og:locale" content="es_ES">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{meta_title}">
  <meta name="twitter:description" content="{meta_description}">

  <!-- SEO adicional -->
  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
  <meta name="geo.region" content="ES">
  <meta name="geo.placename" content="{nombre}">

  <!-- Structured Data -->
  {schemas_json}

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=DM+Serif+Display&display=swap" rel="stylesheet">
  <style>
    :root {{
      --color-primary: #0f172a;
      --color-secondary: #1e293b;
      --color-accent: #d97706;
      --color-accent-light: #f59e0b;
      --color-success: #059669;
      --color-success-light: #dcfce7;
      --color-info: #0284c7;
      --color-info-light: #dbeafe;
      --color-warning: #92400e;
      --color-warning-light: #fef3c7;
      --color-text: #1e293b;
      --color-text-muted: #64748b;
      --color-text-light: #475569;
      --color-bg: #ffffff;
      --color-bg-light: #f8fafc;
      --color-bg-warm: #fffbeb;
      --color-border: #e5e7eb;
      --font-display: 'DM Serif Display', Georgia, serif;
      --font-body: 'DM Sans', system-ui, sans-serif;
      --shadow-sm: 0 2px 8px rgba(0,0,0,0.05);
      --shadow-md: 0 8px 24px rgba(0,0,0,0.12);
      --radius-sm: 6px;
      --radius-md: 12px;
      --radius-lg: 15px;
      --radius-full: 9999px;
    }}

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      font-family: var(--font-body);
      color: var(--color-text);
      background: var(--color-bg-light);
      line-height: 1.6;
    }}

    .provincia-page {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 40px 20px;
    }}

    /* ===== SELECTOR DE PROVINCIAS ===== */
    .provincia-selector {{
      background: var(--color-bg);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 20px 30px;
      margin-bottom: 30px;
      box-shadow: var(--shadow-sm);
    }}

    .provincia-selector-title {{
      font-family: var(--font-display);
      font-size: 1.1em;
      margin-bottom: 15px;
      color: var(--color-text);
    }}

    .provincia-buttons {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}

    .provincia-btn {{
      padding: 10px 20px;
      border: 2px solid var(--color-border);
      border-radius: var(--radius-full);
      background: var(--color-bg);
      color: var(--color-text);
      font-family: var(--font-body);
      font-size: 0.9em;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      text-decoration: none;
    }}

    .provincia-btn:hover {{
      border-color: var(--color-accent);
      background: var(--color-bg-warm);
    }}

    .provincia-btn.active {{
      background: var(--color-primary);
      border-color: var(--color-primary);
      color: white;
    }}

    /* ===== INTRO SECTION ===== */
    .intro-section {{
      background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%);
      color: white;
      padding: 60px 40px;
      border-radius: var(--radius-lg);
      margin-bottom: 40px;
      text-align: center;
      position: relative;
      overflow: hidden;
    }}

    .intro-section::before {{
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
      pointer-events: none;
    }}

    .intro-section h1 {{
      font-family: var(--font-display);
      font-size: 2.5em;
      margin-bottom: 20px;
      font-weight: 400;
      position: relative;
    }}

    .intro-section p {{
      font-size: 1.1em;
      line-height: 1.8;
      max-width: 900px;
      margin: 0 auto 30px;
      opacity: 0.95;
    }}

    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 20px;
      margin-top: 30px;
    }}

    .stat-box {{
      background: rgba(255, 255, 255, 0.1);
      padding: 25px 20px;
      border-radius: var(--radius-md);
      text-align: center;
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.1);
    }}

    .stat-number {{
      font-family: var(--font-display);
      font-size: 2.8em;
      font-weight: 400;
      color: var(--color-accent-light);
      display: block;
      margin-bottom: 8px;
    }}

    .stat-label {{
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      opacity: 0.9;
    }}

    /* ===== LOADING ===== */
    .loading {{
      text-align: center;
      padding: 60px 20px;
    }}

    .loading-spinner {{
      width: 50px;
      height: 50px;
      border: 4px solid var(--color-border);
      border-top-color: var(--color-accent);
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin: 0 auto 20px;
    }}

    @keyframes spin {{
      to {{ transform: rotate(360deg); }}
    }}

    /* ===== SUBASTA CARDS ===== */
    .subastas-grid {{
      display: grid;
      gap: 30px;
    }}

    .subasta-card {{
      background: var(--color-bg);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 30px;
      box-shadow: var(--shadow-sm);
      transition: all 0.3s ease;
    }}

    .subasta-card:hover {{
      box-shadow: var(--shadow-md);
      transform: translateY(-2px);
    }}

    .subasta-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 20px;
      flex-wrap: wrap;
      gap: 15px;
    }}

    .subasta-title {{
      font-family: var(--font-display);
      font-size: 1.3em;
      font-weight: 400;
      color: var(--color-text);
      margin: 0 0 8px 0;
    }}

    .subasta-title a {{
      color: inherit;
      text-decoration: none;
    }}

    .subasta-title a:hover {{
      color: var(--color-accent);
    }}

    .subasta-ref {{
      font-size: 0.85em;
      color: var(--color-text-muted);
      font-family: 'SF Mono', 'Consolas', monospace;
      background: var(--color-bg-light);
      padding: 5px 12px;
      border-radius: var(--radius-sm);
    }}

    .badge {{
      display: inline-block;
      padding: 8px 16px;
      border-radius: var(--radius-full);
      font-size: 0.8em;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}

    .badge-success {{
      background: var(--color-success-light);
      color: #166534;
    }}

    .badge-info {{
      background: var(--color-info-light);
      color: #1e40af;
    }}

    .badge-warning {{
      background: var(--color-warning-light);
      color: var(--color-warning);
    }}

    .badge-lotes {{
      background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
      color: white;
    }}

    .badges-container {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}

    .subasta-card.multi-lotes {{
      border: 2px solid #3b82f6;
      position: relative;
    }}

    .subasta-card.multi-lotes::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 4px;
      background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
      border-radius: var(--radius-md) var(--radius-md) 0 0;
    }}

    .subasta-info-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 15px;
      margin-bottom: 20px;
    }}

    .info-item {{
      padding: 15px;
      background: var(--color-bg-light);
      border-radius: var(--radius-sm);
    }}

    .info-label {{
      font-size: 0.8em;
      color: var(--color-text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 5px;
    }}

    .info-value {{
      font-size: 1em;
      font-weight: 500;
      color: var(--color-text);
    }}

    .precio-destacado {{
      color: var(--color-accent);
      font-weight: 600;
      font-size: 1.1em;
    }}

    .btn-ver-subasta {{
      display: inline-block;
      padding: 12px 25px;
      background: var(--color-primary);
      color: white;
      border-radius: var(--radius-sm);
      text-decoration: none;
      font-weight: 500;
      transition: background 0.2s;
      margin-top: 15px;
    }}

    .btn-ver-subasta:hover {{
      background: var(--color-secondary);
    }}

    /* ===== CTA SECTION ===== */
    .cta-section {{
      background: linear-gradient(135deg, var(--color-accent) 0%, #b45309 100%);
      color: white;
      padding: 50px 40px;
      border-radius: var(--radius-lg);
      margin-top: 50px;
      text-align: center;
    }}

    .cta-section h2 {{
      font-family: var(--font-display);
      font-size: 2em;
      margin-bottom: 20px;
    }}

    .cta-section p {{
      font-size: 1.1em;
      max-width: 700px;
      margin: 0 auto 30px;
      opacity: 0.95;
    }}

    .cta-btn {{
      display: inline-block;
      padding: 15px 35px;
      background: white;
      color: var(--color-accent);
      border-radius: var(--radius-sm);
      text-decoration: none;
      font-weight: 600;
      font-size: 1.1em;
      transition: transform 0.2s;
    }}

    .cta-btn:hover {{
      transform: scale(1.05);
    }}

    /* ===== BREADCRUMBS ===== */
    .breadcrumbs {{
      padding: 15px 0;
      margin-bottom: 20px;
      font-size: 0.9em;
    }}

    .breadcrumbs a {{
      color: var(--color-accent);
      text-decoration: none;
    }}

    .breadcrumbs a:hover {{
      text-decoration: underline;
    }}

    .breadcrumbs span {{
      color: var(--color-text-muted);
      margin: 0 8px;
    }}

    /* ===== SEO CONTENT ===== */
    .seo-content {{
      background: var(--color-bg);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 40px;
      margin-top: 40px;
      line-height: 1.8;
    }}

    .seo-content h2 {{
      font-family: var(--font-display);
      font-size: 1.6em;
      color: var(--color-primary);
      margin-bottom: 20px;
    }}

    .seo-content h3 {{
      font-family: var(--font-display);
      font-size: 1.3em;
      color: var(--color-secondary);
      margin: 25px 0 15px;
    }}

    .seo-content p {{
      color: var(--color-text);
      margin-bottom: 15px;
    }}

    .seo-content ul, .seo-content ol {{
      margin: 15px 0 15px 25px;
      color: var(--color-text);
    }}

    .seo-content li {{
      margin-bottom: 8px;
    }}

    /* ===== FAQ SECTION ===== */
    .faq-section {{
      background: var(--color-bg);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 40px;
      margin-top: 40px;
    }}

    .faq-section h2 {{
      font-family: var(--font-display);
      font-size: 1.6em;
      color: var(--color-primary);
      margin-bottom: 25px;
    }}

    .faq-item-wrapper {{
      margin-bottom: 12px;
    }}

    .faq-item {{
      border: 1px solid var(--color-border);
      border-radius: var(--radius-sm);
      overflow: hidden;
    }}

    .faq-item summary {{
      padding: 18px 20px;
      cursor: pointer;
      font-weight: 600;
      color: var(--color-text);
      background: var(--color-bg-light);
      list-style: none;
      display: flex;
      align-items: center;
    }}

    .faq-item summary::before {{
      content: '+';
      font-size: 1.3em;
      font-weight: 700;
      color: var(--color-accent);
      margin-right: 12px;
      flex-shrink: 0;
    }}

    .faq-item[open] summary::before {{
      content: '\u2212';
    }}

    .faq-item summary::-webkit-details-marker {{
      display: none;
    }}

    .faq-answer {{
      padding: 18px 20px;
      color: var(--color-text-light);
      line-height: 1.7;
      border-top: 1px solid var(--color-border);
    }}

    /* ===== RESPONSIVE ===== */
    @media (max-width: 768px) {{
      .intro-section {{ padding: 40px 25px; }}
      .intro-section h1 {{ font-size: 1.8em; }}
      .provincia-selector {{ padding: 15px 20px; }}
      .provincia-btn {{ padding: 8px 15px; font-size: 0.85em; }}
      .subasta-card {{ padding: 20px; }}
      .seo-content, .faq-section {{ padding: 25px; }}
    }}
  </style>
</head>
<body>

<div class="provincia-page">

  <!-- ===== BREADCRUMBS ===== -->
  <nav class="breadcrumbs" aria-label="Migas de pan">
    <a href="/">Inicio</a>
    <span>\u203a</span>
    <a href="/subastas-judiciales/">Subastas Judiciales</a>
    <span>\u203a</span>
    <strong>{nombre}</strong>
  </nav>

  <!-- ===== SELECTOR DE PROVINCIAS ===== -->
  <nav class="provincia-selector" aria-label="Selector de provincias">
    <h3 class="provincia-selector-title">Subastas por Provincia en Espa\u00f1a</h3>
    <details>
      <summary style="cursor:pointer;font-weight:500;margin-bottom:10px;">Ver todas las provincias (52)</summary>
      <div class="provincia-buttons">
        <a href="/subastas-judiciales-a-coruna/" class="provincia-btn{' active' if slug == 'a-coruna' else ''}">A Coruña</a>
        <a href="/subastas-judiciales-alava/" class="provincia-btn{' active' if slug == 'alava' else ''}">Álava</a>
        <a href="/subastas-judiciales-albacete/" class="provincia-btn{' active' if slug == 'albacete' else ''}">Albacete</a>
        <a href="/subastas-judiciales-alicante/" class="provincia-btn{' active' if slug == 'alicante' else ''}">Alicante</a>
        <a href="/subastas-judiciales-almeria/" class="provincia-btn{' active' if slug == 'almeria' else ''}">Almería</a>
        <a href="/subastas-judiciales-asturias/" class="provincia-btn{' active' if slug == 'asturias' else ''}">Asturias</a>
        <a href="/subastas-judiciales-avila/" class="provincia-btn{' active' if slug == 'avila' else ''}">Ávila</a>
        <a href="/subastas-judiciales-badajoz/" class="provincia-btn{' active' if slug == 'badajoz' else ''}">Badajoz</a>
        <a href="/subastas-judiciales-baleares/" class="provincia-btn{' active' if slug == 'baleares' else ''}">Baleares</a>
        <a href="/subastas-judiciales-barcelona/" class="provincia-btn{' active' if slug == 'barcelona' else ''}">Barcelona</a>
        <a href="/subastas-judiciales-burgos/" class="provincia-btn{' active' if slug == 'burgos' else ''}">Burgos</a>
        <a href="/subastas-judiciales-caceres/" class="provincia-btn{' active' if slug == 'caceres' else ''}">Cáceres</a>
        <a href="/subastas-judiciales-cadiz/" class="provincia-btn{' active' if slug == 'cadiz' else ''}">Cádiz</a>
        <a href="/subastas-judiciales-cantabria/" class="provincia-btn{' active' if slug == 'cantabria' else ''}">Cantabria</a>
        <a href="/subastas-judiciales-castellon/" class="provincia-btn{' active' if slug == 'castellon' else ''}">Castellón</a>
        <a href="/subastas-judiciales-ceuta/" class="provincia-btn{' active' if slug == 'ceuta' else ''}">Ceuta</a>
        <a href="/subastas-judiciales-ciudad-real/" class="provincia-btn{' active' if slug == 'ciudad-real' else ''}">Ciudad Real</a>
        <a href="/subastas-judiciales-cordoba/" class="provincia-btn{' active' if slug == 'cordoba' else ''}">Córdoba</a>
        <a href="/subastas-judiciales-cuenca/" class="provincia-btn{' active' if slug == 'cuenca' else ''}">Cuenca</a>
        <a href="/subastas-judiciales-girona/" class="provincia-btn{' active' if slug == 'girona' else ''}">Girona</a>
        <a href="/subastas-judiciales-granada/" class="provincia-btn{' active' if slug == 'granada' else ''}">Granada</a>
        <a href="/subastas-judiciales-guadalajara/" class="provincia-btn{' active' if slug == 'guadalajara' else ''}">Guadalajara</a>
        <a href="/subastas-judiciales-guipuzcoa/" class="provincia-btn{' active' if slug == 'guipuzcoa' else ''}">Guipúzcoa</a>
        <a href="/subastas-judiciales-huelva/" class="provincia-btn{' active' if slug == 'huelva' else ''}">Huelva</a>
        <a href="/subastas-judiciales-huesca/" class="provincia-btn{' active' if slug == 'huesca' else ''}">Huesca</a>
        <a href="/subastas-judiciales-jaen/" class="provincia-btn{' active' if slug == 'jaen' else ''}">Jaén</a>
        <a href="/subastas-judiciales-la-rioja/" class="provincia-btn{' active' if slug == 'la-rioja' else ''}">La Rioja</a>
        <a href="/subastas-judiciales-las-palmas/" class="provincia-btn{' active' if slug == 'las-palmas' else ''}">Las Palmas</a>
        <a href="/subastas-judiciales-leon/" class="provincia-btn{' active' if slug == 'leon' else ''}">León</a>
        <a href="/subastas-judiciales-lleida/" class="provincia-btn{' active' if slug == 'lleida' else ''}">Lleida</a>
        <a href="/subastas-judiciales-lugo/" class="provincia-btn{' active' if slug == 'lugo' else ''}">Lugo</a>
        <a href="/subastas-judiciales-madrid/" class="provincia-btn{' active' if slug == 'madrid' else ''}">Madrid</a>
        <a href="/subastas-judiciales-malaga/" class="provincia-btn{' active' if slug == 'malaga' else ''}">Málaga</a>
        <a href="/subastas-judiciales-melilla/" class="provincia-btn{' active' if slug == 'melilla' else ''}">Melilla</a>
        <a href="/subastas-judiciales-murcia/" class="provincia-btn{' active' if slug == 'murcia' else ''}">Murcia</a>
        <a href="/subastas-judiciales-navarra/" class="provincia-btn{' active' if slug == 'navarra' else ''}">Navarra</a>
        <a href="/subastas-judiciales-ourense/" class="provincia-btn{' active' if slug == 'ourense' else ''}">Ourense</a>
        <a href="/subastas-judiciales-palencia/" class="provincia-btn{' active' if slug == 'palencia' else ''}">Palencia</a>
        <a href="/subastas-judiciales-pontevedra/" class="provincia-btn{' active' if slug == 'pontevedra' else ''}">Pontevedra</a>
        <a href="/subastas-judiciales-salamanca/" class="provincia-btn{' active' if slug == 'salamanca' else ''}">Salamanca</a>
        <a href="/subastas-judiciales-santa-cruz-tenerife/" class="provincia-btn{' active' if slug == 'santa-cruz-tenerife' else ''}">S.C. Tenerife</a>
        <a href="/subastas-judiciales-segovia/" class="provincia-btn{' active' if slug == 'segovia' else ''}">Segovia</a>
        <a href="/subastas-judiciales-sevilla/" class="provincia-btn{' active' if slug == 'sevilla' else ''}">Sevilla</a>
        <a href="/subastas-judiciales-soria/" class="provincia-btn{' active' if slug == 'soria' else ''}">Soria</a>
        <a href="/subastas-judiciales-tarragona/" class="provincia-btn{' active' if slug == 'tarragona' else ''}">Tarragona</a>
        <a href="/subastas-judiciales-teruel/" class="provincia-btn{' active' if slug == 'teruel' else ''}">Teruel</a>
        <a href="/subastas-judiciales-toledo/" class="provincia-btn{' active' if slug == 'toledo' else ''}">Toledo</a>
        <a href="/subastas-judiciales-valencia/" class="provincia-btn{' active' if slug == 'valencia' else ''}">Valencia</a>
        <a href="/subastas-judiciales-valladolid/" class="provincia-btn{' active' if slug == 'valladolid' else ''}">Valladolid</a>
        <a href="/subastas-judiciales-vizcaya/" class="provincia-btn{' active' if slug == 'vizcaya' else ''}">Vizcaya</a>
        <a href="/subastas-judiciales-zamora/" class="provincia-btn{' active' if slug == 'zamora' else ''}">Zamora</a>
        <a href="/subastas-judiciales-zaragoza/" class="provincia-btn{' active' if slug == 'zaragoza' else ''}">Zaragoza</a>
      </div>
    </details>
  </nav>

  <!-- ===== INTRO SECTION ===== -->
  <section class="intro-section">
    <h1>Subastas Judiciales en {nombre} {current_year}</h1>
    <p>Listado completo y actualizado de <strong>subastas judiciales de inmuebles en {nombre}</strong> ({comunidad}) publicadas en el BOE. Pisos, casas, locales y fincas embargadas con descuentos de hasta el 60%. Asesoramiento legal de CAFAVE INVESTMENT.</p>

    <div class="stats-grid">
      <div class="stat-box">
        <span class="stat-number" id="stats-total">-</span>
        <span class="stat-label">Subastas Activas</span>
      </div>
      <div class="stat-box">
        <span class="stat-number">20%</span>
        <span class="stat-label">Depósito Nuevo Régimen</span>
      </div>
      <div class="stat-box">
        <span class="stat-number">24h</span>
        <span class="stat-label">Actualización Diaria</span>
      </div>
    </div>
  </section>

  <!-- ===== SUBASTAS CONTAINER ===== -->
  <div id="subastas-container">
    <div class="loading">
      <div class="loading-spinner"></div>
      <p>Cargando subastas de {nombre}...</p>
    </div>
  </div>

  <!-- ===== SEO CONTENT (STATIC, INDEXABLE) ===== -->
  {seo_text}

  <!-- ===== FAQ SECTION ===== -->
  {faq_html}

  <!-- ===== CTA SECTION ===== -->
  <section class="cta-section">
    <h2>Asesoramiento Profesional en Subastas Judiciales en {nombre}</h2>
    <p>Nuestro equipo de abogados especializados en {comunidad} analiza cada subasta, verifica cargas registrales y le acompa\u00f1a en todo el proceso de compra en subasta judicial.</p>
    <a href="/contacto/" class="cta-btn" title="Solicitar consulta gratuita subastas {nombre}">Solicitar Consulta Gratuita</a>
  </section>

</div>

<script>
(function() {{
  const API_URL = '{self.base_url}/wp-json/wp/v2';
  const PROVINCIA_SLUG = '{slug}';
  const PROVINCIA = '{nombre}';

  // Función para formatear precios
  function formatPrice(value) {{
    if (!value || value === '0') return 'No disponible';
    const num = parseFloat(value);
    return num.toLocaleString('es-ES', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}) + ' €';
  }}

  // Función para formatear fechas
  function formatDate(dateStr) {{
    if (!dateStr) return 'No disponible';
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-ES', {{
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }});
  }}

  // Renderizar una subasta como card HTML
  function renderCard(subasta) {{
    const meta = subasta.subasta_meta || subasta.meta || {{}};
    const titulo = subasta.title.rendered;
    const link = subasta.link;
    const id = meta._subasta_id || meta['_subasta_id'] || '';
    const valor = formatPrice(meta._subasta_valor || meta['_subasta_valor']);
    const deposito = formatPrice(meta._subasta_deposito || meta['_subasta_deposito']);
    const fechaFin = formatDate(meta._subasta_fecha_fin || meta['_subasta_fecha_fin']);
    const estado = meta._subasta_estado || meta['_subasta_estado'] || 'En curso';
    const tipo = meta._bien_tipo || meta['_bien_tipo'] || 'Inmueble';
    const localidad = meta._bien_localidad || meta['_bien_localidad'] || PROVINCIA;
    const numLotes = parseInt(meta._subasta_num_lotes || meta['_subasta_num_lotes'] || '1');

    let badgeClass = 'badge-info';
    let badgeText = estado;
    if (estado.toLowerCase().includes('celebr')) {{
      badgeClass = 'badge-success';
      badgeText = 'En Curso';
    }}

    const lotesBadge = numLotes > 1 ? `<span class="badge badge-lotes">📦 ${{numLotes}} Lotes</span>` : '';

    return `
      <article class="subasta-card ${{numLotes > 1 ? 'multi-lotes' : ''}}">
        <header class="subasta-header">
          <div>
            <h2 class="subasta-title"><a href="${{link}}">${{titulo}}</a></h2>
            <span class="subasta-ref">Ref: ${{id}}</span>
          </div>
          <div class="badges-container">
            ${{lotesBadge}}
            <span class="badge ${{badgeClass}}">${{badgeText}}</span>
          </div>
        </header>
        <div class="subasta-info-grid">
          <div class="info-item">
            <div class="info-label">💰 Valor Subasta${{numLotes > 1 ? ' (Total)' : ''}}</div>
            <div class="info-value precio-destacado">${{valor}}</div>
          </div>
          <div class="info-item">
            <div class="info-label">🏷️ Depósito${{numLotes > 1 ? ' (Total)' : ''}}</div>
            <div class="info-value">${{deposito}}</div>
          </div>
          <div class="info-item">
            <div class="info-label">📅 Finaliza</div>
            <div class="info-value">${{fechaFin}}</div>
          </div>
          <div class="info-item">
            <div class="info-label">🏠 Tipo</div>
            <div class="info-value">${{tipo}}</div>
          </div>
          <div class="info-item">
            <div class="info-label">📍 Localidad</div>
            <div class="info-value">${{localidad}}</div>
          </div>
        </div>
        <a href="${{link}}" class="btn-ver-subasta">Ver Detalles Completos →</a>
      </article>
    `;
  }}

  // Cargar todas las subastas con paginación
  async function loadSubastas() {{
    try {{
      const catResponse = await fetch(`${{API_URL}}/categories?slug=${{PROVINCIA_SLUG}}`);
      const categories = await catResponse.json();

      if (!categories || categories.length === 0) {{
        document.getElementById('stats-total').textContent = '0';
        document.getElementById('subastas-container').innerHTML = `
          <div style="text-align: center; padding: 60px 20px;">
            <p style="font-size: 1.2em; color: var(--color-text-muted);">
              No hay subastas activas en ${{PROVINCIA}} en este momento.
            </p>
            <p style="margin-top: 15px;">Vuelva a consultar pronto o explore otras provincias.</p>
          </div>
        `;
        return;
      }}

      const categoriaId = categories[0].id;
      const container = document.getElementById('subastas-container');

      // Primera página: renderizar inmediatamente
      const firstResponse = await fetch(`${{API_URL}}/posts?categories=${{categoriaId}}&per_page=100&page=1&_embed`);
      const totalPages = parseInt(firstResponse.headers.get('X-WP-TotalPages') || '1');
      const totalPosts = parseInt(firstResponse.headers.get('X-WP-Total') || '0');
      const firstBatch = await firstResponse.json();

      if (firstBatch.length === 0) {{
        document.getElementById('stats-total').textContent = '0';
        container.innerHTML = `
          <div style="text-align: center; padding: 60px 20px;">
            <p style="font-size: 1.2em; color: var(--color-text-muted);">
              No hay subastas activas en ${{PROVINCIA}} en este momento.
            </p>
            <p style="margin-top: 15px;">Vuelva a consultar pronto o explore otras provincias.</p>
          </div>
        `;
        return;
      }}

      // Mostrar total y primera página de resultados sin esperar al resto
      document.getElementById('stats-total').textContent = totalPosts;
      container.innerHTML = '<div class="subastas-grid" id="subastas-grid"></div>';
      const grid = document.getElementById('subastas-grid');
      grid.innerHTML = firstBatch.map(renderCard).join('');

      // Cargar páginas restantes en segundo plano
      for (let page = 2; page <= totalPages; page++) {{
        const resp = await fetch(`${{API_URL}}/posts?categories=${{categoriaId}}&per_page=100&page=${{page}}&_embed`);
        const batch = await resp.json();
        grid.insertAdjacentHTML('beforeend', batch.map(renderCard).join(''));
      }}

    }} catch (error) {{
      console.error('Error cargando subastas:', error);
      const container = document.getElementById('subastas-container');
      if (!container.querySelector('.subasta-card')) {{
        container.innerHTML = `
          <div style="text-align: center; padding: 60px 20px; color: var(--color-warning);">
            <p>Error al cargar las subastas. Por favor, recargue la página.</p>
          </div>
        `;
      }}
    }}
  }}

  // Cargar al iniciar
  loadSubastas();
}})();
</script>

</body>
</html>
<!-- /wp:html -->'''

    def _set_seo_meta(self, page_id: int, provincia_codigo: str, stats: Optional[dict] = None):
        """Sets Rank Math and Yoast SEO meta fields for a province page.

        Accepts optional `stats` from create_page to avoid duplicate DB queries.
        """
        prov = PROVINCIAS_ESPANA[provincia_codigo]
        nombre = prov["nombre"]
        slug = prov["slug"]
        comunidad = prov.get("comunidad", "España")
        current_year = datetime.now(timezone.utc).year
        page_url = f"https://comprarensubasta.com/subastas-judiciales-{slug}/"

        if stats is None:
            stats = self._get_provincia_stats(provincia_codigo)
        total_activas = stats.get("total_activas", 0)

        meta_title = self._build_meta_title(nombre, current_year, total_activas)
        meta_desc = (
            f"Subastas judiciales en {nombre} {current_year}. "
            f"Listado actualizado de pisos, casas, locales y fincas embargadas en {nombre} ({comunidad}). "
            f"Descuentos del 30-60%. Asesoramiento legal gratuito."
        )
        if len(meta_desc) > 160:
            meta_desc = meta_desc[:157] + "..."
        focus_kw = f"subastas judiciales {nombre.lower()}"

        meta_fields = {
            # Rank Math
            "rank_math_title": meta_title,
            "rank_math_description": meta_desc,
            "rank_math_focus_keyword": focus_kw,
            "rank_math_canonical_url": page_url,
            "rank_math_robots": ["index", "follow", "max-snippet:-1", "max-image-preview:large"],
            # Yoast
            "_yoast_wpseo_title": meta_title,
            "_yoast_wpseo_metadesc": meta_desc,
            "_yoast_wpseo_focuskw": focus_kw,
            "_yoast_wpseo_canonical": page_url,
            "_yoast_wpseo_opengraph-title": meta_title,
            "_yoast_wpseo_opengraph-description": meta_desc,
            "_yoast_wpseo_twitter-title": meta_title,
            "_yoast_wpseo_twitter-description": meta_desc,
        }

        try:
            requests.post(
                f"{self.base_url}/wp-json/wp/v2/pages/{page_id}",
                auth=self.auth,
                json={"meta": meta_fields}
            )
        except Exception:
            pass  # Non-critical, page content already has meta tags

    def create_page(self, provincia_codigo: str, update_existing: bool = True) -> dict:
        """
        Crea o actualiza una página de provincia en WordPress.
        Sets SEO meta fields (Rank Math + Yoast) after creation/update.
        """
        prov = PROVINCIAS_ESPANA.get(provincia_codigo)
        if not prov:
            raise ValueError(f"Código de provincia no válido: {provincia_codigo}")

        current_year = datetime.now(timezone.utc).year
        slug = f"subastas-judiciales-{prov['slug']}"
        stats = self._get_provincia_stats(provincia_codigo)
        title = self._build_meta_title(prov["nombre"], current_year, stats["total_activas"])
        content = self.generate_page_content(provincia_codigo, stats=stats)

        # Verificar si ya existe
        existing = self._get_existing_page(slug)

        if existing and update_existing:
            response = requests.post(
                f"{self.base_url}/wp-json/wp/v2/pages/{existing['id']}",
                auth=self.auth,
                json={
                    "title": title,
                    "content": content,
                    "status": "publish"
                }
            )
            result = response.json()
            page_id = result.get("id")
            if page_id:
                self._set_seo_meta(page_id, provincia_codigo, stats=stats)
            return {
                "action": "updated",
                "id": page_id,
                "slug": slug,
                "provincia": prov["nombre"]
            }
        elif not existing:
            response = requests.post(
                f"{self.base_url}/wp-json/wp/v2/pages",
                auth=self.auth,
                json={
                    "title": title,
                    "content": content,
                    "slug": slug,
                    "status": "publish"
                }
            )
            result = response.json()
            page_id = result.get("id")
            if page_id:
                self._set_seo_meta(page_id, provincia_codigo, stats=stats)
            return {
                "action": "created",
                "id": page_id,
                "slug": slug,
                "provincia": prov["nombre"]
            }
        else:
            return {
                "action": "skipped",
                "id": existing["id"],
                "slug": slug,
                "provincia": prov["nombre"]
            }

    def _get_existing_page(self, slug: str) -> Optional[dict]:
        """Busca una página existente por slug."""
        response = requests.get(
            f"{self.base_url}/wp-json/wp/v2/pages",
            params={"slug": slug}
        )
        pages = response.json()
        return pages[0] if pages else None

    def generate_index_page_content(self) -> str:
        """
        Genera el contenido HTML para la página índice de subastas
        con enlaces a todas las provincias organizadas por comunidad autónoma.
        """
        # Agrupar provincias por comunidad autónoma
        comunidades = {}
        for codigo, data in PROVINCIAS_ESPANA.items():
            comunidad = data.get("comunidad", "Otras")
            if comunidad not in comunidades:
                comunidades[comunidad] = []
            comunidades[comunidad].append({
                "codigo": codigo,
                "nombre": data["nombre"],
                "slug": data["slug"]
            })

        # Ordenar comunidades y provincias
        comunidades_ordenadas = sorted(comunidades.keys())
        for comunidad in comunidades_ordenadas:
            comunidades[comunidad].sort(key=lambda x: x["nombre"])

        # Generar HTML de las provincias por comunidad
        provincias_html = ""
        for comunidad in comunidades_ordenadas:
            provincias_html += f'''
        <div class="comunidad-section">
          <h3 class="comunidad-title">{comunidad}</h3>
          <div class="provincias-grid">
'''
            for prov in comunidades[comunidad]:
                provincias_html += f'''            <a href="/subastas-judiciales-{prov['slug']}/" class="provincia-card">
              <span class="provincia-name">{prov['nombre']}</span>
              <span class="provincia-arrow">→</span>
            </a>
'''
            provincias_html += '''          </div>
        </div>
'''

        current_year = datetime.now(timezone.utc).year
        site_url = "https://comprarensubasta.com"
        page_url = f"{site_url}/subastas-judiciales/"
        meta_title = f"Subastas Judiciales en Espa\u00f1a {current_year} - Todas las Provincias | Comprar en Subasta"
        meta_description = (
            f"Subastas judiciales de inmuebles en las 52 provincias de Espa\u00f1a {current_year}. "
            "Pisos, casas, locales y fincas embargadas del BOE. Listado actualizado diariamente."
        )

        index_breadcrumb = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Inicio", "item": site_url},
                {"@type": "ListItem", "position": 2, "name": "Subastas Judiciales", "item": page_url}
            ]
        }

        index_webpage = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": meta_title,
            "description": meta_description,
            "url": page_url,
            "isPartOf": {"@type": "WebSite", "name": "Comprar en Subasta", "url": site_url},
            "provider": {
                "@type": "LegalService",
                "name": "CAFAVE INVESTMENT",
                "url": site_url
            },
            "inLanguage": "es"
        }

        return f'''<!-- wp:html -->
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{meta_title}</title>
  <meta name="description" content="{meta_description}">
  <link rel="canonical" href="{page_url}">

  <!-- Open Graph -->
  <meta property="og:type" content="website">
  <meta property="og:url" content="{page_url}">
  <meta property="og:title" content="{meta_title}">
  <meta property="og:description" content="{meta_description}">
  <meta property="og:site_name" content="Comprar en Subasta - CAFAVE INVESTMENT">
  <meta property="og:locale" content="es_ES">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{meta_title}">
  <meta name="twitter:description" content="{meta_description}">

  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">

  <script type="application/ld+json">
{json.dumps(index_breadcrumb, ensure_ascii=False, indent=2)}
  </script>
  <script type="application/ld+json">
{json.dumps(index_webpage, ensure_ascii=False, indent=2)}
  </script>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
  <style>
    :root {{
      --color-primary: #0f172a;
      --color-secondary: #1e293b;
      --color-accent: #d97706;
      --color-accent-light: #f59e0b;
      --color-text: #1e293b;
      --color-text-muted: #64748b;
      --color-bg: #ffffff;
      --color-bg-light: #f8fafc;
      --color-bg-warm: #fffbeb;
      --color-border: #e5e7eb;
      --font-display: 'DM Serif Display', Georgia, serif;
      --font-body: 'DM Sans', system-ui, sans-serif;
      --shadow-sm: 0 2px 8px rgba(0,0,0,0.05);
      --shadow-md: 0 8px 24px rgba(0,0,0,0.12);
      --radius-sm: 6px;
      --radius-md: 12px;
      --radius-lg: 15px;
    }}

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      font-family: var(--font-body);
      color: var(--color-text);
      background: var(--color-bg-light);
      line-height: 1.6;
    }}

    .subastas-index {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 40px 20px;
    }}

    /* Hero Section */
    .hero-section {{
      background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%);
      color: white;
      padding: 60px 40px;
      border-radius: var(--radius-lg);
      margin-bottom: 50px;
      text-align: center;
      position: relative;
      overflow: hidden;
    }}

    .hero-section::before {{
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
      pointer-events: none;
    }}

    .hero-section h1 {{
      font-family: var(--font-display);
      font-size: 2.8em;
      margin-bottom: 20px;
      font-weight: 400;
      position: relative;
    }}

    .hero-section p {{
      font-size: 1.15em;
      line-height: 1.8;
      max-width: 800px;
      margin: 0 auto;
      opacity: 0.95;
    }}

    .stats-bar {{
      display: flex;
      justify-content: center;
      gap: 40px;
      margin-top: 35px;
      flex-wrap: wrap;
    }}

    .stat-item {{
      text-align: center;
    }}

    .stat-number {{
      font-family: var(--font-display);
      font-size: 2.5em;
      color: var(--color-accent-light);
      display: block;
    }}

    .stat-label {{
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 1px;
      opacity: 0.9;
    }}

    /* Comunidad Sections */
    .comunidad-section {{
      margin-bottom: 40px;
    }}

    .comunidad-title {{
      font-family: var(--font-display);
      font-size: 1.5em;
      color: var(--color-primary);
      margin-bottom: 20px;
      padding-bottom: 10px;
      border-bottom: 2px solid var(--color-accent);
      display: inline-block;
    }}

    .provincias-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 15px;
    }}

    .provincia-card {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 18px 20px;
      background: var(--color-bg);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-sm);
      text-decoration: none;
      color: var(--color-text);
      transition: all 0.2s ease;
      box-shadow: var(--shadow-sm);
    }}

    .provincia-card:hover {{
      border-color: var(--color-accent);
      background: var(--color-bg-warm);
      transform: translateY(-2px);
      box-shadow: var(--shadow-md);
    }}

    .provincia-name {{
      font-weight: 500;
    }}

    .provincia-arrow {{
      color: var(--color-accent);
      font-size: 1.2em;
      transition: transform 0.2s;
    }}

    .provincia-card:hover .provincia-arrow {{
      transform: translateX(5px);
    }}

    /* Info Section */
    .info-section {{
      background: var(--color-bg);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 40px;
      margin-top: 50px;
    }}

    .info-section h2 {{
      font-family: var(--font-display);
      font-size: 1.8em;
      margin-bottom: 20px;
      color: var(--color-primary);
    }}

    .info-section p {{
      color: var(--color-text-muted);
      margin-bottom: 15px;
    }}

    .info-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 25px;
      margin-top: 30px;
    }}

    .info-card {{
      padding: 25px;
      background: var(--color-bg-light);
      border-radius: var(--radius-sm);
    }}

    .info-card h3 {{
      font-size: 1.1em;
      margin-bottom: 10px;
      color: var(--color-primary);
    }}

    .info-card p {{
      font-size: 0.95em;
      margin: 0;
    }}

    /* CTA Section */
    .cta-section {{
      background: linear-gradient(135deg, var(--color-accent) 0%, #b45309 100%);
      color: white;
      padding: 50px 40px;
      border-radius: var(--radius-lg);
      margin-top: 50px;
      text-align: center;
    }}

    .cta-section h2 {{
      font-family: var(--font-display);
      font-size: 2em;
      margin-bottom: 15px;
    }}

    .cta-section p {{
      font-size: 1.1em;
      max-width: 600px;
      margin: 0 auto 25px;
      opacity: 0.95;
    }}

    .cta-btn {{
      display: inline-block;
      padding: 15px 35px;
      background: white;
      color: var(--color-accent);
      border-radius: var(--radius-sm);
      text-decoration: none;
      font-weight: 600;
      font-size: 1.1em;
      transition: transform 0.2s;
    }}

    .cta-btn:hover {{
      transform: scale(1.05);
    }}

    /* Responsive */
    @media (max-width: 768px) {{
      .hero-section {{ padding: 40px 25px; }}
      .hero-section h1 {{ font-size: 2em; }}
      .stats-bar {{ gap: 25px; }}
      .provincias-grid {{ grid-template-columns: 1fr; }}
      .info-section {{ padding: 25px; }}
    }}
  </style>
</head>
<body>

<div class="subastas-index">

  <!-- Breadcrumbs -->
  <nav style="padding:15px 0;margin-bottom:20px;font-size:0.9em;" aria-label="Migas de pan">
    <a href="/" style="color:#d97706;text-decoration:none;">Inicio</a>
    <span style="color:#64748b;margin:0 8px;">\u203a</span>
    <strong>Subastas Judiciales</strong>
  </nav>

  <!-- Hero Section -->
  <section class="hero-section">
    <h1>Subastas Judiciales en Espa\u00f1a {current_year}</h1>
    <p>Acceda a todas las <strong>subastas judiciales del BOE</strong> organizadas por provincia. Listado actualizado diariamente con las mejores oportunidades de inversi\u00f3n inmobiliaria en toda Espa\u00f1a. Pisos, casas, locales y fincas embargadas con descuentos de hasta el 60%.</p>

    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-number">52</span>
        <span class="stat-label">Provincias</span>
      </div>
      <div class="stat-item">
        <span class="stat-number">24h</span>
        <span class="stat-label">Actualización</span>
      </div>
      <div class="stat-item">
        <span class="stat-number">100%</span>
        <span class="stat-label">Oficial BOE</span>
      </div>
    </div>
  </section>

  <!-- Provincias por Comunidad Autónoma -->
  <div class="provincias-container">
{provincias_html}
  </div>

  <!-- Info Section -->
  <section class="info-section">
    <h2>¿Cómo funcionan las subastas judiciales?</h2>
    <p>Las subastas judiciales son procedimientos legales donde se venden bienes embargados para saldar deudas. Representan una excelente oportunidad para adquirir inmuebles por debajo del precio de mercado.</p>

    <div class="info-grid">
      <div class="info-card">
        <h3>Depósito del 20%</h3>
        <p>Para participar necesita depositar el 20% del valor de tasación como garantía.</p>
      </div>
      <div class="info-card">
        <h3>Proceso 100% Online</h3>
        <p>Las subastas se realizan de forma electrónica a través del Portal de Subastas del BOE.</p>
      </div>
      <div class="info-card">
        <h3>Asesoramiento Legal</h3>
        <p>Recomendamos contar con asesoramiento profesional para analizar cargas y documentación.</p>
      </div>
    </div>
  </section>

  <!-- CTA Section -->
  <section class="cta-section">
    <h2>¿Necesita Ayuda Profesional?</h2>
    <p>Nuestro equipo de expertos puede analizar las oportunidades y gestionar todo el proceso de compra.</p>
    <a href="/contacto/" class="cta-btn">Solicitar Consulta Gratuita</a>
  </section>

</div>

</body>
</html>
<!-- /wp:html -->'''

    def _set_index_seo_meta(self, page_id: int):
        """Sets SEO meta fields for the index page."""
        current_year = datetime.now(timezone.utc).year
        meta_title = f"Subastas Judiciales en España {current_year} - Todas las Provincias | Comprar en Subasta"
        meta_desc = (
            f"Subastas judiciales de inmuebles en las 52 provincias de España {current_year}. "
            "Pisos, casas, locales y fincas embargadas del BOE. Listado actualizado diariamente."
        )
        page_url = "https://comprarensubasta.com/subastas-judiciales/"
        focus_kw = "subastas judiciales españa"

        meta_fields = {
            "rank_math_title": meta_title,
            "rank_math_description": meta_desc,
            "rank_math_focus_keyword": focus_kw,
            "rank_math_canonical_url": page_url,
            "_yoast_wpseo_title": meta_title,
            "_yoast_wpseo_metadesc": meta_desc,
            "_yoast_wpseo_focuskw": focus_kw,
            "_yoast_wpseo_canonical": page_url,
            "_yoast_wpseo_opengraph-title": meta_title,
            "_yoast_wpseo_opengraph-description": meta_desc,
        }

        try:
            requests.post(
                f"{self.base_url}/wp-json/wp/v2/pages/{page_id}",
                auth=self.auth,
                json={"meta": meta_fields}
            )
        except Exception:
            pass

    def create_index_page(self, update_existing: bool = True) -> dict:
        """
        Crea o actualiza la página índice de subastas.
        """
        current_year = datetime.now(timezone.utc).year
        slug = "subastas-judiciales"
        title = f"Subastas Judiciales en España {current_year} | Todas las Provincias"
        content = self.generate_index_page_content()

        # Verificar si ya existe
        existing = self._get_existing_page(slug)

        if existing and update_existing:
            response = requests.post(
                f"{self.base_url}/wp-json/wp/v2/pages/{existing['id']}",
                auth=self.auth,
                json={
                    "title": title,
                    "content": content,
                    "status": "publish"
                }
            )
            result = response.json()
            page_id = result.get("id")
            if page_id:
                self._set_index_seo_meta(page_id)
            return {
                "action": "updated",
                "id": page_id,
                "slug": slug,
                "url": f"{self.base_url}/{slug}/"
            }
        elif not existing:
            response = requests.post(
                f"{self.base_url}/wp-json/wp/v2/pages",
                auth=self.auth,
                json={
                    "title": title,
                    "content": content,
                    "slug": slug,
                    "status": "publish"
                }
            )
            result = response.json()
            page_id = result.get("id")
            if page_id:
                self._set_index_seo_meta(page_id)
            return {
                "action": "created",
                "id": page_id,
                "slug": slug,
                "url": f"{self.base_url}/{slug}/"
            }
        else:
            return {
                "action": "skipped",
                "id": existing["id"],
                "slug": slug,
                "url": f"{self.base_url}/{slug}/"
            }

    def create_all_pages(self) -> list:
        """Crea páginas para todas las 52 provincias de España."""
        results = []
        total = len(PROVINCIAS_ESPANA)
        for i, codigo in enumerate(sorted(PROVINCIAS_ESPANA.keys()), 1):
            try:
                result = self.create_page(codigo)
                results.append(result)
                print(f"  [{i}/{total}] {result['action'].upper()}: {result['provincia']} - ID: {result['id']}")
            except Exception as e:
                print(f"  [{i}/{total}] ERROR: {PROVINCIAS_ESPANA[codigo]['nombre']} - {e}")
                results.append({
                    "action": "error",
                    "id": None,
                    "provincia": PROVINCIAS_ESPANA[codigo]['nombre'],
                    "error": str(e)
                })
        return results


if __name__ == "__main__":
    generator = ProvinciaPageGenerator()
    print("═" * 60)
    print("  CREANDO PÁGINAS DE LAS 52 PROVINCIAS DE ESPAÑA")
    print("═" * 60)
    results = generator.create_all_pages()
    print("═" * 60)
    created = len([r for r in results if r['action'] == 'created'])
    updated = len([r for r in results if r['action'] == 'updated'])
    errors = len([r for r in results if r['action'] == 'error'])
    print(f"  Creadas: {created} | Actualizadas: {updated} | Errores: {errors}")
    print("═" * 60)
