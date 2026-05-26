"""
Publicador de subastas en WordPress.
Genera contenido HTML y publica posts usando el cliente WordPress.
"""
import logging
import urllib.parse
from typing import List, Optional
from datetime import datetime

from .client import WordPressClient
from ..models.subasta import Subasta, Bien

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import settings
from config.provinces import get_provincia_nombre, get_provincia_slug


logger = logging.getLogger(__name__)


class WordPressPublisher:
    """Publica subastas en WordPress."""

    def __init__(self, client: WordPressClient = None):
        """
        Inicializa el publicador.

        Args:
            client: Cliente WordPress (opcional, se crea uno por defecto)
        """
        self.client = client or WordPressClient()
        self.contact_url = settings.WP_CONTACT_FORM_URL

    def publish_subasta(self, subasta: Subasta, update_if_exists: bool = True) -> int:
        """
        Publica o actualiza una subasta en WordPress.

        Args:
            subasta: Objeto Subasta a publicar
            update_if_exists: Si True, actualiza si ya existe

        Returns:
            ID del post creado/actualizado
        """
        # Verificar si ya existe (slug determinista + búsqueda por contenido)
        existing_post = self._find_existing_post(subasta.id_subasta)

        # OG image: si Pillow está disponible y el upload tiene éxito,
        # tendremos URL pública + media_id; en caso contrario, los
        # generadores caen a un og:image por defecto del sitio (sin romper).
        og_image_url, og_image_id = self._get_or_create_og_image(subasta)

        # Generar contenido
        title = self._generate_title(subasta)
        content = self._generate_content(subasta, og_image_url=og_image_url)
        categories = self._get_categories(subasta)
        tags = self._get_tags(subasta)
        # Pasamos `existing_post` para que la canonical preserve la URL ya
        # indexada (slug histórico) en updates y use el slug determinista en
        # posts nuevos.
        meta = self._generate_meta(
            subasta,
            existing_post=existing_post,
            og_image_url=og_image_url,
        )

        post_data = {
            "title": title,
            "content": content,
            "status": settings.WP_POST_STATUS,
            "categories": categories,
            "tags": tags,
            "meta": meta,
        }
        if og_image_id:
            post_data["featured_media"] = og_image_id

        if existing_post and update_if_exists:
            # Actualizar post existente. NO tocamos el slug para no romper
            # URLs ya indexadas en buscadores; los posts antiguos conservan su
            # slug original (la búsqueda por contenido los encuentra igual).
            post_id = existing_post["id"]
            self.client.update_post(post_id, post_data)
            logger.info(f"Post actualizado: {post_id} - {subasta.id_subasta}")
            return post_id
        else:
            # Posts nuevos: slug determinista para que get_post_by_subasta_id
            # los encuentre en O(1) en futuras ejecuciones.
            post_data["slug"] = self.client.make_subasta_slug(subasta.id_subasta)
            result = self.client.create_post(**post_data)
            post_id = result["id"]
            logger.info(f"Post creado: {post_id} - {subasta.id_subasta}")
            return post_id

    def _find_existing_post(self, id_subasta: str) -> Optional[dict]:
        """Busca un post existente para una subasta."""
        return self.client.get_post_by_subasta_id(id_subasta)

    def _get_or_create_og_image(self, subasta: Subasta) -> tuple:
        """Genera y sube la OG image. Devuelve (url, media_id) o (None, None).

        Si Pillow no está disponible o el upload falla, no rompe el flujo:
        devuelve (None, None) y el caller usa el og:image default.
        """
        try:
            from .og_image import get_or_create_og_image
        except ImportError:
            return None, None

        bien = subasta.get_bien_principal()
        tipo = bien.subtipo_bien if bien and bien.subtipo_bien else "Inmueble"
        localidad = bien.localidad if bien and bien.localidad else "España"
        provincia = bien.provincia if bien and bien.provincia else ""

        precio_str = "Consultar"
        if subasta.valor_subasta and float(subasta.valor_subasta) > 0:
            precio_str = f"{float(subasta.valor_subasta):,.0f}€".replace(",", ".")

        return get_or_create_og_image(
            tipo=tipo,
            localidad=localidad,
            precio_str=precio_str,
            provincia=provincia,
            wp_client=self.client,
        )

    def _generate_title(self, subasta: Subasta) -> str:
        """
        Genera el título SEO-optimizado del post.

        Máximo 60 caracteres para evitar truncamiento en Google SERPs.
        Prioridad: tipo + localidad > precio > provincia.
        """
        bien = subasta.get_bien_principal()

        # Tipo de inmueble (abreviar tipos largos)
        tipo = "Inmueble"
        if bien and bien.subtipo_bien:
            raw = bien.subtipo_bien.title()
            # Abreviar tipos que alargan el título
            abreviaturas = {
                "Vivienda Unifamiliar": "Casa",
                "Vivienda Unifamiliar Adosada": "Adosado",
                "Vivienda Unifamiliar Pareada": "Pareado",
                "Local Comercial": "Local",
                "Nave Industrial": "Nave",
                "Plaza De Garaje": "Garaje",
                "Finca Rústica": "Finca",
                "Finca Urbana": "Finca Urbana",
                "Solar Sin Edificar": "Solar",
            }
            tipo = abreviaturas.get(raw, raw)

        # Localidad
        localidad = "España"
        if bien and bien.localidad:
            localidad = bien.localidad.title()

        # Precio formateado
        precio_str = ""
        if subasta.valor_subasta and float(subasta.valor_subasta) > 0:
            precio = float(subasta.valor_subasta)
            if precio >= 1000:
                precio_str = f" desde {precio:,.0f}€".replace(",", ".")

        # Provincia (solo si diferente a localidad)
        provincia_str = ""
        if bien and bien.provincia and bien.provincia.lower() != localidad.lower():
            provincia_str = f" ({bien.provincia})"

        # Construir título respetando límite de 60 chars
        base = f"Subasta {tipo} en {localidad}"
        if len(base + precio_str + provincia_str) <= 60:
            return base + precio_str + provincia_str
        if len(base + precio_str) <= 60:
            return base + precio_str
        if len(base + provincia_str) <= 60:
            return base + provincia_str
        if len(base) <= 60:
            return base
        # Último recurso: truncar
        return base[:57] + "..."

    def _generate_meta_description(self, subasta: Subasta) -> str:
        """
        Genera la meta description SEO-optimizada.

        Formato: "🏠 Subasta judicial de [tipo] en [localidad], [provincia].
                  Valor: [precio]€. Finaliza [fecha]. Asesoramiento legal gratuito."

        Máximo 155-160 caracteres para evitar truncamiento en Google.
        """
        bien = subasta.get_bien_principal()

        # Tipo de inmueble
        tipo = "inmueble"
        if bien and bien.subtipo_bien:
            tipo = bien.subtipo_bien.lower()

        # Ubicación
        localidad = bien.localidad if bien and bien.localidad else "España"
        provincia = bien.provincia if bien and bien.provincia else ""

        ubicacion = localidad
        if provincia and provincia.lower() != localidad.lower():
            ubicacion = f"{localidad}, {provincia}"

        # Precio
        precio_str = "Consultar precio"
        if subasta.valor_subasta and float(subasta.valor_subasta) > 0:
            precio = float(subasta.valor_subasta)
            precio_str = f"{precio:,.0f}€".replace(",", ".")

        # Fecha de finalización
        fecha_str = ""
        if subasta.fecha_conclusion:
            fecha_str = f" Finaliza {subasta.fecha_conclusion.strftime('%d/%m/%Y')}."

        # Construir descripción (máx 160 chars)
        descripcion = f"Subasta judicial de {tipo} en {ubicacion}. Valor: {precio_str}.{fecha_str} Asesoramiento legal gratuito."

        # Truncar si excede 160 caracteres
        if len(descripcion) > 160:
            descripcion = descripcion[:157] + "..."

        return descripcion

    def _generate_schema_markup(self, subasta: Subasta, og_image_url: Optional[str] = None) -> str:
        """
        Genera Schema.org JSON-LD para rich snippets en Google.

        Incluye: RealEstateListing, BreadcrumbList, LegalService.
        NO incluye BlogPosting (Rank Math lo desactiva via meta).

        Si `og_image_url` se provee, se añade al schema RealEstateListing.image[]
        y al organizationSchema (Sprint 2 — Acción 3).
        """
        import json

        bien = subasta.get_bien_principal()

        # Datos básicos
        tipo = bien.subtipo_bien if bien and bien.subtipo_bien else "Inmueble"
        localidad = bien.localidad if bien and bien.localidad else "España"
        provincia = bien.provincia if bien and bien.provincia else "España"
        direccion = bien.direccion if bien and bien.direccion else ""
        codigo_postal = bien.codigo_postal if bien and bien.codigo_postal else ""
        provincia_slug = get_provincia_slug(bien.provincia_codigo) if bien and bien.provincia_codigo else ""

        # Precio
        precio = float(subasta.valor_subasta) if subasta.valor_subasta else 0

        # Fecha disponibilidad (fecha conclusión)
        fecha_disponible = ""
        if subasta.fecha_conclusion:
            fecha_disponible = subasta.fecha_conclusion.strftime("%Y-%m-%d")

        site_url = "https://comprarensubasta.com"

        # Schema 1: BreadcrumbList
        breadcrumb_items = [
            {"@type": "ListItem", "position": 1, "name": "Inicio", "item": site_url},
            {"@type": "ListItem", "position": 2, "name": "Subastas Judiciales", "item": f"{site_url}/subastas-judiciales/"},
        ]
        if provincia_slug:
            breadcrumb_items.append({
                "@type": "ListItem", "position": 3,
                "name": f"Subastas en {provincia}",
                "item": f"{site_url}/subastas-judiciales-{provincia_slug}/"
            })
            breadcrumb_items.append({
                "@type": "ListItem", "position": 4,
                "name": f"Subasta {tipo} en {localidad}"
            })
        else:
            breadcrumb_items.append({
                "@type": "ListItem", "position": 3,
                "name": f"Subasta {tipo} en {localidad}"
            })

        breadcrumb_schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": breadcrumb_items
        }

        # Schema 2: RealEstateListing
        # dateModified ayuda a Google a entender la frescura del listado.
        # image[] habilita rich snippet visual (Sprint 2 — A3).
        offer = {
            "@type": "Offer",
            "price": precio,
            "priceCurrency": "EUR",
            "availability": "https://schema.org/InStock",
            "seller": {
                "@type": "Organization",
                "name": subasta.autoridad_gestora or "Portal de Subastas BOE",
            },
        }
        if fecha_disponible:
            offer["validThrough"] = fecha_disponible

        schema = {
            "@context": "https://schema.org",
            "@type": "RealEstateListing",
            "name": f"Subasta {tipo} en {localidad}",
            "description": self._generate_meta_description(subasta),
            "url": subasta.url_detalle or f"https://subastas.boe.es/detalleSubasta.php?idSub={subasta.id_subasta}",
            "datePosted": subasta.fecha_inicio.strftime("%Y-%m-%d") if subasta.fecha_inicio else "",
            "dateModified": datetime.now().strftime("%Y-%m-%d"),
            "offers": offer,
        }
        if og_image_url:
            schema["image"] = [og_image_url]

        # Añadir ubicación si hay datos
        if direccion or localidad:
            schema["contentLocation"] = {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": direccion,
                    "addressLocality": localidad,
                    "addressRegion": provincia,
                    "postalCode": codigo_postal,
                    "addressCountry": "ES"
                }
            }

        # Schema 3: LegalService (para el despacho)
        org_schema = {
            "@context": "https://schema.org",
            "@type": "LegalService",
            "name": "CAFAVE INVESTMENT - Comprar en Subasta",
            "description": "Asesoramiento legal especializado en subastas judiciales e inmobiliarias en España",
            "url": site_url,
            "areaServed": {
                "@type": "Country",
                "name": "España"
            },
            "serviceType": ["Asesoramiento legal en subastas", "Gestión de pujas", "Análisis de cargas registrales", "Mandatos de compra en subasta"]
        }

        return f'''<script type="application/ld+json">
{json.dumps(breadcrumb_schema, ensure_ascii=False, indent=2)}
</script>
<script type="application/ld+json">
{json.dumps(schema, ensure_ascii=False, indent=2)}
</script>
<script type="application/ld+json">
{json.dumps(org_schema, ensure_ascii=False, indent=2)}
</script>'''

    def _faq_items(self, subasta: Subasta) -> List[tuple]:
        """Fuente única de las FAQs (Sprint 2 — Acción 8).

        Tanto `_generate_faq_schema` (JSON-LD) como `_generate_faq_html`
        (HTML visible) consumen esta lista. Esto garantiza que el número y
        contenido de preguntas siempre coincide — requisito de Google Rich
        Results para FAQPage (mismatch = pérdida del snippet).

        Cada elemento es una tupla `(question, answer)` con strings ya
        personalizados con los datos de la subasta.
        """
        bien = subasta.get_bien_principal()

        tipo = bien.subtipo_bien if bien and bien.subtipo_bien else "inmueble"
        localidad = bien.localidad if bien and bien.localidad else "esta ubicación"

        precio_str = "consultar en la documentación"
        if subasta.valor_subasta and float(subasta.valor_subasta) > 0:
            precio_str = f"{float(subasta.valor_subasta):,.0f}€".replace(",", ".")

        deposito_str = "el 5% del valor de subasta"
        if subasta.importe_deposito and float(subasta.importe_deposito) > 0:
            deposito_str = f"{float(subasta.importe_deposito):,.0f}€".replace(",", ".")

        fecha_str = "consultar en el BOE"
        if subasta.fecha_conclusion:
            fecha_str = subasta.fecha_conclusion.strftime("%d/%m/%Y a las %H:%M")

        return [
            (
                f"¿Cuál es el valor de salida de esta subasta de {tipo} en {localidad}?",
                f"El valor de salida de esta subasta es de {precio_str}. Este es el precio mínimo desde el que pueden comenzar las pujas. Recuerda que en subastas judiciales puedes adquirir inmuebles por debajo del valor de mercado.",
            ),
            (
                "¿Cuánto depósito necesito para participar en esta subasta?",
                f"Para participar en esta subasta necesitas depositar {deposito_str}. Este depósito se realiza a través del Portal de Subastas del BOE y se devuelve si no resultas adjudicatario.",
            ),
            (
                "¿Hasta cuándo puedo pujar en esta subasta?",
                f"Esta subasta finaliza el {fecha_str}. Te recomendamos registrarte con antelación en el Portal de Subastas del BOE y tener preparada la documentación necesaria.",
            ),
            (
                "¿Qué documentación necesito para participar en una subasta judicial?",
                "Para participar necesitas: DNI/NIE vigente, certificado digital o Cl@ve, cuenta bancaria para el depósito, y estar dado de alta en el Portal de Subastas del BOE. Recomendamos también revisar el edicto y la certificación de cargas antes de pujar.",
            ),
            (
                f"¿Es seguro comprar un {tipo} en subasta judicial?",
                "Sí, las subastas judiciales son procedimientos legales supervisados por juzgados. Sin embargo, es fundamental analizar las cargas registrales y la situación posesoria antes de pujar. Te recomendamos contar con asesoramiento legal especializado para evitar sorpresas.",
            ),
            (
                "¿Qué pasa si gano la subasta? ¿Cuáles son los siguientes pasos?",
                "Si ganas la subasta, deberás pagar el resto del precio en el plazo establecido (normalmente 20 días hábiles), liquidar los impuestos correspondientes (ITP o IVA), y esperar el Decreto de Adjudicación para inscribir la propiedad en el Registro. Un abogado especializado puede gestionar todo el proceso.",
            ),
        ]

    def _generate_faq_schema(self, subasta: Subasta) -> str:
        """FAQ Schema JSON-LD (consume `_faq_items` para no descompensar
        con la versión HTML — Acción 8)."""
        import json

        faqs = [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in self._faq_items(subasta)
        ]
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faqs,
        }

        return f'''<script type="application/ld+json">
{json.dumps(faq_schema, ensure_ascii=False, indent=2)}
</script>'''

    def _generate_faq_html(self, subasta: Subasta) -> str:
        """HTML visible de las FAQs. Usa `<details>/<summary>` para mejor
        a11y y conserva el mismo conjunto de preguntas que el JSON-LD.
        """
        items = self._faq_items(subasta)
        body = "\n".join(
            f'        <details class="faq-item">\n'
            f'            <summary>{q}</summary>\n'
            f'            <p>{a}</p>\n'
            f'        </details>'
            for q, a in items
        )
        return f'''
    <!-- FAQ Section — fuente única en _faq_items (Acción 8) -->
    <section class="subasta-faq">
        <h2>Preguntas Frecuentes sobre esta Subasta</h2>
{body}
    </section>
'''

    def _generate_content(self, subasta: Subasta, og_image_url: Optional[str] = None) -> str:
        """
        Genera el contenido HTML SEO-optimizado del post.

        Incluye:
        - Schema.org JSON-LD para rich snippets
        - Estructura semántica con H2/H3
        - Palabras clave naturales en el contenido
        - CTA optimizado
        """
        bien = subasta.get_bien_principal()

        # Formatear valores monetarios
        def format_money(value):
            try:
                return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
            except (TypeError, ValueError):
                return "No disponible"

        # Formatear fechas
        def format_date(dt):
            if dt:
                return dt.strftime("%d/%m/%Y a las %H:%M")
            return "No disponible"

        # Estado con estilo. `subasta.estado` puede ser None si el scraper
        # no lo extrajo: usamos un default antes de aplicar `.lower()`.
        estado_texto = (subasta.estado or "En curso").strip()
        estado_class = "en-curso" if "celebr" in estado_texto.lower() else "proxima"

        # Datos para SEO contextual
        tipo_bien = bien.subtipo_bien if bien and bien.subtipo_bien else "inmueble"
        localidad = bien.localidad if bien and bien.localidad else "España"
        provincia = bien.provincia if bien and bien.provincia else "España"

        # Schema markup JSON-LD (RealEstateListing + Organization)
        schema_markup = self._generate_schema_markup(subasta, og_image_url=og_image_url)

        # FAQ Schema JSON-LD (para Google e IAs)
        faq_schema = self._generate_faq_schema(subasta)

        # Estilos CSS para múltiples lotes y mapa
        css_styles = """
<style>
/* Estilos para múltiples lotes */
.subasta-alerta.multi-lotes {
    background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
    color: white;
    padding: 20px;
    border-radius: 10px;
    margin-bottom: 25px;
    text-align: center;
}
.subasta-alerta.multi-lotes strong {
    font-size: 1.3em;
    display: block;
    margin-bottom: 8px;
}
.subasta-alerta.multi-lotes p {
    margin: 0;
    opacity: 0.9;
}
.bien-lote {
    border: 2px solid #e5e7eb;
    border-radius: 12px;
    padding: 25px;
    margin-bottom: 30px;
    background: #fafafa;
}
.bien-lote h2 {
    color: #1e40af;
    border-bottom: 2px solid #3b82f6;
    padding-bottom: 10px;
    margin-bottom: 20px;
}

/* Estilos para la ubicación (link card, sin iframe — Sprint 2 A4) */
.mapa-ubicacion {
    margin-top: 25px;
    padding: 20px;
    background: #f0f9ff;
    border-radius: 10px;
    border: 1px solid #bae6fd;
}
.mapa-ubicacion h3 {
    color: #0369a1;
    margin-bottom: 15px;
}
.mapa-link-card {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 18px 20px;
    background: #fff;
    border: 1px solid #bae6fd;
    border-radius: 8px;
    text-decoration: none;
    color: #1e293b;
    transition: background .2s, border-color .2s;
}
.mapa-link-card:hover {
    background: #f0f9ff;
    border-color: #0284c7;
}
.mapa-link-card svg { flex-shrink: 0; }
.mapa-link-text { display: flex; flex-direction: column; gap: 4px; }
.mapa-link-text strong { color: #0f172a; }
.mapa-link-text small { color: #0369a1; font-size: 0.9em; }

/* Breadcrumbs */
.breadcrumbs {
    font-size: 0.85em;
    color: #6b7280;
    margin-bottom: 20px;
    padding: 10px 0;
}
.breadcrumbs a {
    color: #2563eb;
    text-decoration: none;
}
.breadcrumbs a:hover {
    text-decoration: underline;
}

/* Estilos para valores económicos del lote */
.valores-lote {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    border: 2px solid #f59e0b;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
}
.valores-lote h3 {
    color: #92400e;
    margin-bottom: 15px;
    font-size: 1.1em;
}
.tabla-valores-lote {
    width: 100%;
    border-collapse: collapse;
}
.tabla-valores-lote th {
    text-align: left;
    padding: 8px 12px;
    background: rgba(255,255,255,0.5);
    border-bottom: 1px solid #f59e0b;
    color: #78350f;
    font-weight: 500;
    width: 40%;
}
.tabla-valores-lote td {
    padding: 8px 12px;
    border-bottom: 1px solid rgba(245,158,11,0.3);
    color: #1f2937;
}
.tabla-valores-lote .precio {
    color: #b45309;
    font-size: 1.1em;
}
</style>
"""

        # Breadcrumbs HTML visible
        provincia_slug = get_provincia_slug(bien.provincia_codigo) if bien and bien.provincia_codigo else ""
        breadcrumb_html = '<nav class="breadcrumbs" aria-label="Breadcrumb"><span><a href="/">Inicio</a></span>'
        breadcrumb_html += ' &rsaquo; <span><a href="/subastas-judiciales/">Subastas</a></span>'
        if provincia_slug and provincia:
            breadcrumb_html += f' &rsaquo; <span><a href="/subastas-judiciales-{provincia_slug}/">{provincia}</a></span>'
        breadcrumb_html += f' &rsaquo; <span>{tipo_bien.title()} en {localidad}</span></nav>'

        html = f"""{schema_markup}
{faq_schema}
{css_styles}
<div class="subasta-detalle">

    <!-- Breadcrumbs -->
    {breadcrumb_html}

    <!-- Alerta de Estado -->
    <div class="subasta-alerta {estado_class}">
        <strong>🔔 {estado_texto.upper()}</strong>
        {f' - Finaliza: {format_date(subasta.fecha_conclusion)}' if subasta.fecha_conclusion else ''}
    </div>

    <!-- Información General - H2 con palabra clave -->
    <div class="subasta-seccion">
        <h2>Detalles de la Subasta Judicial en {localidad}</h2>
        <p class="intro-seo">Esta <strong>subasta de {tipo_bien}</strong> en <strong>{localidad}</strong> ({provincia})
        está disponible a través del <strong>Portal de Subastas del BOE</strong>.
        Consulta todos los detalles y solicita asesoramiento legal gratuito.</p>
        <table class="tabla-subasta">
            <tr>
                <th>Identificador</th>
                <td><strong>{subasta.id_subasta}</strong></td>
            </tr>
            <tr>
                <th>Tipo de Subasta</th>
                <td>{subasta.tipo_subasta or 'Judicial'}</td>
            </tr>
            <tr>
                <th>Valor de Subasta</th>
                <td><strong class="precio">{format_money(subasta.valor_subasta)}</strong></td>
            </tr>
            <tr>
                <th>Tasación</th>
                <td>{format_money(subasta.tasacion)}</td>
            </tr>
            <tr>
                <th>Depósito Requerido</th>
                <td>{format_money(subasta.importe_deposito)}</td>
            </tr>
            <tr>
                <th>Puja Mínima</th>
                <td>{format_money(subasta.puja_minima) if subasta.puja_minima > 0 else 'Sin puja mínima'}</td>
            </tr>
            <tr>
                <th>Tramos entre Pujas</th>
                <td>{format_money(subasta.tramos_pujas)}</td>
            </tr>
            <tr>
                <th>Fecha de Inicio</th>
                <td>{format_date(subasta.fecha_inicio)}</td>
            </tr>
            <tr>
                <th>Fecha de Conclusión</th>
                <td>{format_date(subasta.fecha_conclusion)}</td>
            </tr>
        </table>
    </div>
"""

        # Sección de bienes - TODOS los lotes
        num_bienes = len(subasta.bienes)

        if num_bienes > 0:
            # Si hay múltiples lotes, mostrar encabezado especial
            if num_bienes > 1:
                html += f"""
    <!-- Aviso de múltiples lotes -->
    <div class="subasta-alerta multi-lotes">
        <strong>📦 Esta subasta incluye {num_bienes} LOTES</strong>
        <p>A continuación se detallan todos los bienes incluidos en esta subasta.</p>
    </div>
"""

            # Iterar sobre TODOS los bienes
            for idx, bien in enumerate(subasta.bienes, 1):
                lote_titulo = f"LOTE {idx}: " if num_bienes > 1 else ""

                # Valores económicos del lote (si hay múltiples lotes)
                valores_lote_html = ""
                if num_bienes > 1 and (bien.valor_subasta_lote > 0 or bien.importe_deposito_lote > 0):
                    valores_lote_html = f"""
        <!-- Valores económicos del lote -->
        <div class="valores-lote">
            <h3>💰 Valores Económicos del Lote {idx}</h3>
            <table class="tabla-valores-lote">
                <tr>
                    <th>Valor Subasta</th>
                    <td><strong class="precio">{format_money(bien.valor_subasta_lote)}</strong></td>
                </tr>
                <tr>
                    <th>Tasación</th>
                    <td>{format_money(bien.valor_tasacion)}</td>
                </tr>
                <tr>
                    <th>Depósito Requerido</th>
                    <td>{format_money(bien.importe_deposito_lote)}</td>
                </tr>
                <tr>
                    <th>Puja Mínima</th>
                    <td>{format_money(bien.puja_minima_lote) if bien.puja_minima_lote > 0 else 'Sin puja mínima'}</td>
                </tr>
                <tr>
                    <th>Tramos entre Pujas</th>
                    <td>{format_money(bien.tramos_pujas_lote)}</td>
                </tr>
            </table>
        </div>
"""

                html += f"""
    <!-- Datos del Inmueble {idx} - H2 con contexto geográfico -->
    <div class="subasta-seccion bien-lote" id="lote-{idx}">
        <h2>{lote_titulo}Datos del {bien.subtipo_bien or 'Inmueble'} en {bien.localidad or 'Venta'}</h2>
{valores_lote_html}
        <table class="tabla-bien">
            <tr>
                <th>Tipo de Bien</th>
                <td>{bien.subtipo_bien or bien.tipo_bien or 'Inmueble'}</td>
            </tr>
            <tr>
                <th>Dirección</th>
                <td>{bien.direccion or 'No especificada'}</td>
            </tr>
            <tr>
                <th>Localidad</th>
                <td>{bien.localidad or 'No especificada'}</td>
            </tr>
            <tr>
                <th>Provincia</th>
                <td>{bien.provincia or 'España'}</td>
            </tr>
            <tr>
                <th>Código Postal</th>
                <td>{bien.codigo_postal or 'No especificado'}</td>
            </tr>
            <tr>
                <th>Situación Posesoria</th>
                <td>{bien.situacion_posesoria or 'Consultar en documentación'}</td>
            </tr>
            <tr>
                <th>Visitable</th>
                <td>{bien.visitable or 'Consultar'}</td>
            </tr>
        </table>
"""
                # Mapa de Google Maps si hay dirección
                if bien.direccion and bien.localidad:
                    # Limpiar dirección para Google Maps
                    import re
                    # urllib.parse ya importado al inicio del módulo. NO re-importar
                    # aquí dentro: rompe el scope local de la función (urllib se
                    # vuelve UnboundLocalVariable si la rama no se ejecuta).

                    def limpiar_direccion_para_maps(direccion: str) -> str:
                        """
                        Limpia la dirección del BOE para que Google Maps la reconozca mejor.
                        Maneja casos como:
                        - "Nº82" sin espacio -> "Nº 82"
                        - "PORTAL 4, LOCAL G" -> elimina detalles de piso/local
                        - "planta 2º A de la Calle X, hoy Calle Y" -> usa la dirección actual
                        """
                        if not direccion:
                            return ""

                        d = direccion

                        # 1. Si hay "hoy Calle X", usar la dirección actual (prioritario)
                        if 'hoy ' in d.lower():
                            match = re.search(r'hoy\s+((?:Calle|CL|C/|Avenida|Av|Avda|Plaza|Paseo)[^,]*(?:,?\s*(?:nº|n\.|núm\.?|número)?\s*\d+)?)', d, re.IGNORECASE)
                            if match:
                                d = match.group(1).strip()
                                # Limpiar "de Sevilla" al final si está
                                d = re.sub(r'\s+de\s+\w+$', '', d)

                        # 2. Si empieza con "planta X de la Calle...", extraer solo la calle
                        elif d.lower().startswith(('planta', 'piso', 'local', 'bajo', 'ático', 'atico', 'puerta')):
                            match = re.search(r'(?:de la |de |en la |en )?((?:Calle|CL|C/|Avenida|Av|Avda|Plaza|Pz|Paseo|Camino|Carretera|Ctra)[^,]*)', d, re.IGNORECASE)
                            if match:
                                d = match.group(1).strip()

                        # 3. Separar "Nº82" -> "Nº 82", "nº15" -> "nº 15", "N.12" -> "N. 12"
                        d = re.sub(r'(Nº|nº|N\.|n\.|Num\.?|núm\.?)(\d)', r'\1 \2', d)

                        # 4. Eliminar detalles de planta/puerta/portal/local que confunden a Maps
                        # Incluye patrones como 'PL 2ª -69', 'PISO 3', 'PTA 4', etc.
                        patrones_eliminar = [
                            r'\s+PL\s*\d+[ªº]?\s*[-]?\s*\d*',  # PL 2ª -69, PL 3
                            r'\s+PISO\s*\d+[ªº]?\s*[-]?\s*\w*',  # PISO 2 -4, PISO 3º B
                            r'\s+PTA\.?\s*\d+',  # PTA 4, PTA. 5
                            r'\s+PUERTA\s*\d+',  # PUERTA 3
                            r',?\s*\b(?:planta|piso|pta|puerta|pto|portal|local|bajo|entreplanta|entr|escalera|esc)\b\s*[^,]*',
                            r',\s*\d+[ªº]\s*(?:DERECHA|IZQUIERDA|IZDA?|IZQ|DCHA?|DCH|CENTRO|CTR|[A-Z])\b.*$',  # ', 2º DERECHA', ', 9º D', ', 1ª IZQ' precedido por coma hasta fin
                            r',?\s*\d+[ªº]\s*[A-Za-z]?\s*$',  # '2ª A' al final (sin palabra)
                            r',?\s*(?:bloque|blq|edificio|edif)\s*[^,]*',
                            r'\s*-\s*\d+\s*$',  # ' -69' al final (número de puerta)
                        ]
                        for patron in patrones_eliminar:
                            d = re.sub(patron, '', d, flags=re.IGNORECASE)

                        # 5. Limpiar espacios múltiples y comas sueltas
                        d = re.sub(r'\s+', ' ', d)
                        d = re.sub(r',\s*,', ',', d)
                        d = re.sub(r',\s*$', '', d)
                        d = d.strip(' ,')

                        return d

                    direccion_maps = limpiar_direccion_para_maps(bien.direccion)
                    direccion_completa = f"{direccion_maps}, {bien.localidad}"
                    if bien.provincia:
                        direccion_completa += f", {bien.provincia}"
                    if bien.codigo_postal:
                        direccion_completa += f", {bien.codigo_postal}"
                    direccion_completa += ", España"

                    # Dirección original para mostrar al usuario
                    direccion_original = f"{bien.direccion}, {bien.localidad}"
                    if bien.provincia:
                        direccion_original += f", {bien.provincia}"

                    direccion_encoded = urllib.parse.quote(direccion_completa)

                    # Sprint 2 — Acción 4: sustituimos iframe Google Maps
                    # (~1 MB de JS de terceros, penaliza LCP y exige consent
                    # RGPD) por una tarjeta de enlace con SVG inline. Mismo
                    # affordance visual, peso ~0 KB, sin cookies.
                    html += f"""
        <!-- Ubicación (link a Google Maps, sin iframe pesado — Sprint 2 A4) -->
        <div class="mapa-ubicacion">
            <h3>📍 Ubicación del Inmueble</h3>
            <a href="https://www.google.com/maps/search/?api=1&query={direccion_encoded}"
               target="_blank" rel="noopener noreferrer nofollow"
               class="mapa-link-card"
               aria-label="Abrir ubicación de {bien.subtipo_bien or 'inmueble'} en {bien.localidad} en Google Maps">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 110-5 2.5 2.5 0 010 5z" fill="#d97706"/>
              </svg>
              <span class="mapa-link-text">
                <strong>{direccion_original}</strong>
                <small>Pulsa para abrir en Google Maps →</small>
              </span>
            </a>
        </div>
"""

                if bien.descripcion:
                    html += f"""
        <div class="descripcion-bien">
            <h3>Descripción</h3>
            <p>{bien.descripcion}</p>
        </div>
"""

                if bien.cargas:
                    html += f"""
        <div class="cargas-bien">
            <h3>⚠️ Cargas</h3>
            <p>{bien.cargas}</p>
        </div>
"""
                html += "    </div>\n"

        # Documentos
        html += """
    <!-- Documentos - Importante para confianza -->
    <div class="subasta-seccion">
        <h2>Documentos Oficiales de la Subasta</h2>
        <ul class="lista-documentos">
"""
        if subasta.url_edicto:
            html += f'            <li><a href="{subasta.url_edicto}" target="_blank" rel="noopener noreferrer nofollow">📜 Edicto de la Subasta (PDF)</a></li>\n'
        if subasta.url_certificacion_cargas:
            html += f'            <li><a href="{subasta.url_certificacion_cargas}" target="_blank" rel="noopener noreferrer nofollow">📋 Certificación de Cargas (PDF)</a></li>\n'

        html += f"""        </ul>
    </div>

    <!-- Autoridad Gestora -->
    <div class="subasta-seccion">
        <h2>Juzgado Responsable de la Subasta</h2>
        <p><strong>{subasta.autoridad_gestora or 'Juzgado'}</strong></p>
        <p>Localidad: {subasta.localidad_juzgado or 'No especificada'}</p>
"""
        if subasta.telefono_juzgado:
            html += f"        <p>Teléfono: {subasta.telefono_juzgado}</p>\n"
        if subasta.email_juzgado:
            html += f"        <p>Email: {subasta.email_juzgado}</p>\n"

        html += "    </div>\n"

        # FAQ Section (HTML visible + mejora SEO)
        html += self._generate_faq_html(subasta)

        # CTA - Llamada a la acción.
        # Construimos el href preservando el fragment (#analisis) DESPUÉS del query string;
        # si concatenas "{contact_url}?subasta=..." cuando contact_url ya contiene "#",
        # el navegador trata todo el query como parte del hash y no llega al servidor.
        _cta_parts = urllib.parse.urlsplit(self.contact_url)
        cta_href = urllib.parse.urlunsplit((
            _cta_parts.scheme,
            _cta_parts.netloc,
            _cta_parts.path,
            urllib.parse.urlencode({
                "subasta": subasta.id_subasta,
                "tipo": tipo_bien,
                "localidad": localidad,
                "provincia": provincia,
            }),
            _cta_parts.fragment,
        ))
        html += f"""
    <!-- CTA - Optimizado para conversión -->
    <div class="subasta-cta">
        <h2>Asesoramiento Legal para Subastas en {provincia}</h2>
        <p>¿Quieres <strong>participar en esta subasta judicial</strong>? Nuestro equipo de
        <strong>abogados especializados en subastas</strong> te ayuda con todo el proceso:</p>
        <ul>
            <li>Análisis completo de la documentación y cargas registrales</li>
            <li>Verificación del estado real del inmueble</li>
            <li>Asesoramiento legal durante todo el proceso de puja</li>
            <li>Gestión post-adjudicación y escrituración</li>
        </ul>
        <p><strong>Primera consulta gratuita</strong> - Te explicamos si esta subasta es una buena oportunidad.</p>
        <a href="{cta_href}" class="btn-cta" title="Solicitar análisis gratuito de subasta en {localidad}">
            Solicitar Análisis Gratuito
        </a>
    </div>

    <!-- Enlace BOE -->
    <div class="subasta-enlace-boe">
        <p>
            <a href="{subasta.url_detalle or f'https://subastas.boe.es/detalleSubasta.php?idSub={subasta.id_subasta}'}"
               target="_blank" rel="noopener noreferrer nofollow">
                🔗 Ver subasta original en Portal BOE
            </a>
        </p>
        <p class="aviso-legal">
            <small>
                La información mostrada proviene del Portal de Subastas del BOE.
                Recomendamos verificar los datos directamente en la fuente oficial antes de participar.
            </small>
        </p>
    </div>

</div>
"""
        return html

    def _get_categories(self, subasta: Subasta) -> List[int]:
        """Obtiene o crea las categorías para la subasta."""
        categories = []

        # Categoría principal: Subastas
        subastas_cat = self.client.get_or_create_category("Subastas", "subastas")
        if subastas_cat:
            categories.append(subastas_cat)

        # Categoría por provincia
        bien = subasta.get_bien_principal()
        if bien and bien.provincia:
            provincia_cat = self.client.get_or_create_category(
                bien.provincia,
                get_provincia_slug(bien.provincia_codigo),
                parent=subastas_cat
            )
            if provincia_cat:
                categories.append(provincia_cat)

        # Categoría por tipo de bien
        if bien and bien.subtipo_bien:
            tipo_cat = self.client.get_or_create_category(
                bien.subtipo_bien,
                bien.subtipo_bien.lower().replace(" ", "-"),
                parent=subastas_cat
            )
            if tipo_cat:
                categories.append(tipo_cat)

        return categories

    def _get_tags(self, subasta: Subasta) -> List[int]:
        """Obtiene o crea los tags para la subasta."""
        tags = []
        bien = subasta.get_bien_principal()

        # Tags básicos
        tag_names = ["subasta-boe", "subasta-judicial"]

        # Tag de provincia
        if bien and bien.provincia:
            tag_names.append(bien.provincia.lower().replace(" ", "-"))

        # Tag de localidad
        if bien and bien.localidad:
            tag_names.append(bien.localidad.lower().replace(" ", "-"))

        # Tag de tipo de bien
        if bien and bien.subtipo_bien:
            tag_names.append(bien.subtipo_bien.lower().replace(" ", "-"))

        # Crear tags
        for name in tag_names:
            tag_id = self.client.get_or_create_tag(name)
            if tag_id:
                tags.append(tag_id)

        return tags

    def _generate_meta(
        self,
        subasta: Subasta,
        existing_post: Optional[dict] = None,
        og_image_url: Optional[str] = None,
    ) -> dict:
        """
        Genera los campos meta para el post, incluyendo SEO.

        Args:
            subasta: subasta a serializar.
            existing_post: si ya existe en WP, se usa su `link` como canonical
                para no romper URLs ya indexadas. Si es None, se construye
                desde el slug determinista.
            og_image_url: URL pública de la imagen OG (opcional). Si se provee,
                se propaga a los campos `rank_math_facebook_image` y
                `rank_math_twitter_image`.

        Incluye campos para:
        - Datos internos de la subasta
        - SEO (Rank Math — Yoast eliminado, ver decisión D3 de PLAN_SEO.md)
        - Información de múltiples lotes
        """
        bien = subasta.get_bien_principal()

        # Meta description SEO
        meta_description = self._generate_meta_description(subasta)

        # Título SEO (puede ser ligeramente diferente al título del post)
        tipo = bien.subtipo_bien if bien and bien.subtipo_bien else "Inmueble"
        localidad = bien.localidad if bien and bien.localidad else "España"
        provincia = bien.provincia if bien and bien.provincia else ""

        # URL canónica del post. En updates preservamos `existing_post["link"]`
        # para no romper URLs antiguas ya indexadas (los slugs históricos
        # pueden diferir del slug determinista actual). En posts nuevos, el
        # slug determinista coincide con la canonical.
        canonical_slug = self.client.make_subasta_slug(subasta.id_subasta)
        canonical_url = (existing_post or {}).get("link") or (
            f"{settings.WP_URL.rstrip('/')}/{canonical_slug}/"
        )

        # Focus keyword para SEO
        focus_keyword = f"subasta {tipo.lower()} {localidad.lower()}"

        # SEO title (<60 chars) - priorizar información útil
        seo_title = f"Subasta {tipo} en {localidad} | Comprar en Subasta"
        if len(seo_title) > 60:
            seo_title = f"Subasta {tipo} en {localidad}"
        if len(seo_title) > 60:
            seo_title = seo_title[:57] + "..."

        # OG/Twitter title (puede ser algo más largo, ~95 chars max)
        og_title = f"Subasta {tipo} en {localidad} | Comprar en Subasta"

        # Número de lotes
        num_lotes = len(subasta.bienes)

        # Para subastas multi-lote, calcular valor y depósito totales
        # sumando los valores de cada lote si el valor general es 0
        valor_mostrar = subasta.valor_subasta
        deposito_mostrar = subasta.importe_deposito
        if num_lotes > 1 and valor_mostrar == 0:
            from decimal import Decimal
            valor_mostrar = sum((b.valor_subasta_lote for b in subasta.bienes), Decimal("0"))
            deposito_mostrar = sum((b.importe_deposito_lote for b in subasta.bienes), Decimal("0"))

        meta = {
            # Datos internos de la subasta
            "_subasta_id": subasta.id_subasta,
            "_subasta_tipo": subasta.tipo_subasta or "",
            "_subasta_estado": subasta.estado or "",
            "_subasta_valor": str(valor_mostrar),
            "_subasta_deposito": str(deposito_mostrar),
            "_subasta_fecha_inicio": subasta.fecha_inicio.isoformat() if subasta.fecha_inicio else "",
            "_subasta_fecha_fin": subasta.fecha_conclusion.isoformat() if subasta.fecha_conclusion else "",
            "_subasta_num_lotes": str(num_lotes),

            # SEO - Rank Math (Yoast eliminado, decisión D3 de PLAN_SEO.md)
            "rank_math_title": seo_title,
            "rank_math_description": meta_description,
            "rank_math_focus_keyword": focus_keyword,
            "rank_math_canonical_url": canonical_url,
            "rank_math_robots": ["index", "follow", "max-snippet:-1", "max-image-preview:large"],
            # Disable Rank Math auto-schema (we generate our own JSON-LD)
            "rank_math_rich_snippet": "off",
        }

        # OG image (Sprint 2 — Acción 3). Si og_image_url es None, Rank Math
        # caerá a su fallback (featured image del post o default del sitio).
        if og_image_url:
            meta["rank_math_facebook_image"] = og_image_url
            meta["rank_math_twitter_image"] = og_image_url

        if bien:
            meta.update({
                "_bien_tipo": bien.subtipo_bien or bien.tipo_bien or "",
                "_bien_direccion": bien.direccion or "",
                "_bien_localidad": bien.localidad or "",
                "_bien_provincia": bien.provincia or "",
                "_bien_cp": bien.codigo_postal or "",
            })

        # Si hay múltiples lotes, agregar resumen de tipos y localidad
        if num_lotes > 1:
            tipos_lotes = [b.subtipo_bien or b.tipo_bien or "Inmueble" for b in subasta.bienes]
            meta["_bien_tipo"] = f"{num_lotes} lotes: " + ", ".join(tipos_lotes[:3])
            if num_lotes > 3:
                meta["_bien_tipo"] += f" (+{num_lotes - 3} más)"

            # Usar la primera localidad disponible de cualquier lote
            for b in subasta.bienes:
                if b.localidad:
                    meta["_bien_localidad"] = b.localidad
                    break
                if b.provincia:
                    meta["_bien_provincia"] = b.provincia
                    break

        return meta

    def update_subasta_estado(self, id_subasta: str, nuevo_estado: str) -> bool:
        """
        Actualiza el estado de una subasta ya publicada.

        Args:
            id_subasta: ID de la subasta
            nuevo_estado: Nuevo estado a establecer

        Returns:
            True si se actualizó correctamente
        """
        existing = self._find_existing_post(id_subasta)
        if not existing:
            logger.warning(f"No se encontró post para subasta {id_subasta}")
            return False

        try:
            self.client.update_post(existing["id"], {
                "meta": {"_subasta_estado": nuevo_estado}
            })
            logger.info(f"Estado actualizado para {id_subasta}: {nuevo_estado}")
            return True
        except Exception as e:
            logger.error(f"Error actualizando estado de {id_subasta}: {e}")
            return False

    def despublicar_subasta(self, wp_post_id: int, nuevo_estado: str = "Finalizada") -> bool:
        """
        Despublica una subasta (la pasa a borrador) y actualiza su estado.

        Args:
            wp_post_id: ID del post en WordPress
            nuevo_estado: Nuevo estado a establecer en el meta

        Returns:
            True si se despublicó correctamente
        """
        try:
            # Primero actualizar el estado en el meta
            self.client.update_post(wp_post_id, {
                "meta": {"_subasta_estado": nuevo_estado}
            })

            # Luego despublicar (pasar a borrador)
            result = self.client.unpublish_post(wp_post_id)

            if result:
                logger.info(f"Subasta despublicada: Post ID {wp_post_id} -> Estado: {nuevo_estado}")
            return result

        except Exception as e:
            logger.error(f"Error despublicando subasta (Post ID {wp_post_id}): {e}")
            return False
