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


# JS para el sticky CTA contextual de las fichas de subasta.
# - Aparece tras 30% de scroll (evita flash inicial)
# - Botón cerrar persiste el dismiss en localStorage durante 1h
# Se inyecta una sola vez por post desde _generate_content.
STICKY_CTA_SCRIPT = """
<script>
(function () {
    var STORAGE_KEY = 'sticky_cta_subasta_dismissed_at';
    var DISMISS_MS = 60 * 60 * 1000; // 1h
    var SCROLL_TRIGGER_PCT = 0.30;

    function onReady(fn) {
        if (document.readyState !== 'loading') { fn(); return; }
        document.addEventListener('DOMContentLoaded', fn);
    }

    onReady(function () {
        var el = document.getElementById('sticky-cta-subasta');
        if (!el) return;

        // Respetar dismiss previo (mismo dispositivo, dentro de 1h)
        try {
            var dismissedAt = parseInt(localStorage.getItem(STORAGE_KEY) || '0', 10);
            if (dismissedAt && (Date.now() - dismissedAt < DISMISS_MS)) return;
        } catch (e) { /* localStorage bloqueado: ignorar y seguir */ }

        var shown = false;
        function maybeShow() {
            if (shown) return;
            var scrolled = window.scrollY || window.pageYOffset || 0;
            var docHeight = Math.max(
                document.body.scrollHeight,
                document.documentElement.scrollHeight
            ) - window.innerHeight;
            if (docHeight <= 0) return;
            if (scrolled / docHeight >= SCROLL_TRIGGER_PCT) {
                el.classList.add('visible');
                document.body.classList.add('has-sticky-cta-subasta');
                shown = true;
                window.removeEventListener('scroll', maybeShow);
            }
        }

        window.addEventListener('scroll', maybeShow, { passive: true });
        maybeShow();

        var closeBtn = el.querySelector('[data-sticky-cta-close]');
        if (closeBtn) {
            closeBtn.addEventListener('click', function () {
                el.classList.remove('visible');
                document.body.classList.remove('has-sticky-cta-subasta');
                try { localStorage.setItem(STORAGE_KEY, String(Date.now())); } catch (e) {}
            });
        }
    });
})();
</script>
"""


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

        # Generar contenido
        title = self._generate_title(subasta)
        content = self._generate_content(subasta)
        categories = self._get_categories(subasta)
        tags = self._get_tags(subasta)
        meta = self._generate_meta(subasta)

        post_data = {
            "title": title,
            "content": content,
            "status": settings.WP_POST_STATUS,
            "categories": categories,
            "tags": tags,
            "meta": meta,
        }

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

    def _generate_schema_markup(self, subasta: Subasta) -> str:
        """
        Genera Schema.org JSON-LD para rich snippets en Google.

        Incluye: RealEstateListing, BreadcrumbList, LegalService.
        NO incluye BlogPosting (Rank Math lo desactiva via meta).
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
        schema = {
            "@context": "https://schema.org",
            "@type": "RealEstateListing",
            "name": f"Subasta {tipo} en {localidad}",
            "description": self._generate_meta_description(subasta),
            "url": subasta.url_detalle or f"https://subastas.boe.es/detalleSubasta.php?idSub={subasta.id_subasta}",
            "datePosted": subasta.fecha_inicio.strftime("%Y-%m-%d") if subasta.fecha_inicio else "",
            "offers": {
                "@type": "Offer",
                "price": precio,
                "priceCurrency": "EUR",
                "availability": "https://schema.org/InStock",
                "validThrough": fecha_disponible,
                "seller": {
                    "@type": "Organization",
                    "name": subasta.autoridad_gestora or "Portal de Subastas BOE",
                }
            }
        }

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

    def _generate_faq_schema(self, subasta: Subasta) -> str:
        """
        Genera FAQ Schema JSON-LD para mejorar visibilidad en Google y respuestas de IAs.

        Las preguntas frecuentes se generan dinámicamente basadas en los datos de la subasta.
        Esto ayuda tanto a Google (rich snippets FAQ) como a IAs (ChatGPT, Perplexity, etc.)
        """
        import json

        bien = subasta.get_bien_principal()

        # Datos para personalizar las FAQs
        tipo = bien.subtipo_bien if bien and bien.subtipo_bien else "inmueble"
        localidad = bien.localidad if bien and bien.localidad else "esta ubicación"
        provincia = bien.provincia if bien and bien.provincia else "España"

        # Formatear precio
        precio_str = "consultar en la documentación"
        if subasta.valor_subasta and float(subasta.valor_subasta) > 0:
            precio = float(subasta.valor_subasta)
            precio_str = f"{precio:,.0f}€".replace(",", ".")

        # Formatear depósito
        deposito_str = "el 5% del valor de subasta"
        if subasta.importe_deposito and float(subasta.importe_deposito) > 0:
            deposito = float(subasta.importe_deposito)
            deposito_str = f"{deposito:,.0f}€".replace(",", ".")

        # Formatear fecha
        fecha_str = "consultar en el BOE"
        if subasta.fecha_conclusion:
            fecha_str = subasta.fecha_conclusion.strftime("%d/%m/%Y a las %H:%M")

        # Generar FAQs dinámicas
        faqs = [
            {
                "@type": "Question",
                "name": f"¿Cuál es el valor de salida de esta subasta de {tipo} en {localidad}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"El valor de salida de esta subasta es de {precio_str}. Este es el precio mínimo desde el que pueden comenzar las pujas. Recuerda que en subastas judiciales puedes adquirir inmuebles por debajo del valor de mercado."
                }
            },
            {
                "@type": "Question",
                "name": f"¿Cuánto depósito necesito para participar en esta subasta?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Para participar en esta subasta necesitas depositar {deposito_str}. Este depósito se realiza a través del Portal de Subastas del BOE y se devuelve si no resultas adjudicatario."
                }
            },
            {
                "@type": "Question",
                "name": f"¿Hasta cuándo puedo pujar en esta subasta?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Esta subasta finaliza el {fecha_str}. Te recomendamos registrarte con antelación en el Portal de Subastas del BOE y tener preparada la documentación necesaria."
                }
            },
            {
                "@type": "Question",
                "name": "¿Qué documentación necesito para participar en una subasta judicial?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Para participar necesitas: DNI/NIE vigente, certificado digital o Cl@ve, cuenta bancaria para el depósito, y estar dado de alta en el Portal de Subastas del BOE. Recomendamos también revisar el edicto y la certificación de cargas antes de pujar."
                }
            },
            {
                "@type": "Question",
                "name": f"¿Es seguro comprar un {tipo} en subasta judicial?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Sí, las subastas judiciales son procedimientos legales supervisados por juzgados. Sin embargo, es fundamental analizar las cargas registrales y la situación posesoria antes de pujar. Te recomendamos contar con asesoramiento legal especializado para evitar sorpresas."
                }
            },
            {
                "@type": "Question",
                "name": "¿Qué pasa si gano la subasta? ¿Cuáles son los siguientes pasos?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Si ganas la subasta, deberás pagar el resto del precio en el plazo establecido (normalmente 20 días hábiles), liquidar los impuestos correspondientes (ITP o IVA), y esperar el Decreto de Adjudicación para inscribir la propiedad en el Registro. Un abogado especializado puede gestionar todo el proceso."
                }
            }
        ]

        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faqs
        }

        return f'''<script type="application/ld+json">
{json.dumps(faq_schema, ensure_ascii=False, indent=2)}
</script>'''

    def _generate_faq_html(self, subasta: Subasta) -> str:
        """
        Genera el HTML visible de las FAQs para el contenido del post.

        Este contenido complementa el FAQ Schema y mejora la experiencia del usuario.
        """
        bien = subasta.get_bien_principal()

        tipo = bien.subtipo_bien if bien and bien.subtipo_bien else "inmueble"
        localidad = bien.localidad if bien and bien.localidad else "esta ubicación"

        # Formatear precio
        precio_str = "consultar en la documentación"
        if subasta.valor_subasta and float(subasta.valor_subasta) > 0:
            precio = float(subasta.valor_subasta)
            precio_str = f"{precio:,.0f}€".replace(",", ".")

        # Formatear depósito
        deposito_str = "el 5% del valor de subasta"
        if subasta.importe_deposito and float(subasta.importe_deposito) > 0:
            deposito = float(subasta.importe_deposito)
            deposito_str = f"{deposito:,.0f}€".replace(",", ".")

        # Formatear fecha
        fecha_str = "consultar en el BOE"
        if subasta.fecha_conclusion:
            fecha_str = subasta.fecha_conclusion.strftime("%d/%m/%Y a las %H:%M")

        return f'''
    <!-- FAQ Section - Optimizado para Google e IAs -->
    <div class="subasta-faq">
        <h2>Preguntas Frecuentes sobre esta Subasta</h2>

        <div class="faq-item">
            <h3>¿Cuál es el valor de salida de esta subasta de {tipo} en {localidad}?</h3>
            <p>El valor de salida de esta subasta es de <strong>{precio_str}</strong>. Este es el precio mínimo desde el que pueden comenzar las pujas.</p>
        </div>

        <div class="faq-item">
            <h3>¿Cuánto depósito necesito para participar?</h3>
            <p>Para participar necesitas depositar <strong>{deposito_str}</strong>. Este depósito se realiza a través del Portal de Subastas del BOE.</p>
        </div>

        <div class="faq-item">
            <h3>¿Hasta cuándo puedo pujar?</h3>
            <p>Esta subasta finaliza el <strong>{fecha_str}</strong>. Regístrate con antelación en el Portal de Subastas del BOE.</p>
        </div>

        <div class="faq-item">
            <h3>¿Qué documentación necesito?</h3>
            <p>Necesitas DNI/NIE vigente, certificado digital o Cl@ve, y estar dado de alta en el Portal de Subastas del BOE.</p>
        </div>

        <div class="faq-item">
            <h3>¿Es seguro comprar en subasta judicial?</h3>
            <p>Sí, son procedimientos legales supervisados por juzgados. Recomendamos analizar las cargas y contar con asesoramiento legal.</p>
        </div>
    </div>
'''

    def _generate_content(self, subasta: Subasta) -> str:
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
            except:
                return "No disponible"

        # Formatear fechas
        def format_date(dt):
            if dt:
                return dt.strftime("%d/%m/%Y a las %H:%M")
            return "No disponible"

        # Estado con estilo
        estado_class = "en-curso" if "celebr" in subasta.estado.lower() else "proxima"
        estado_texto = subasta.estado or "En curso"

        # Datos para SEO contextual
        tipo_bien = bien.subtipo_bien if bien and bien.subtipo_bien else "inmueble"
        localidad = bien.localidad if bien and bien.localidad else "España"
        provincia = bien.provincia if bien and bien.provincia else "España"

        # Schema markup JSON-LD (RealEstateListing + Organization)
        schema_markup = self._generate_schema_markup(subasta)

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

/* Estilos para el mapa */
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
.mapa-container {
    margin-bottom: 15px;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.mapa-direccion {
    color: #475569;
    font-size: 0.95em;
    margin-bottom: 15px;
}
.btn-mapa {
    display: inline-block;
    background: #0284c7;
    color: white !important;
    padding: 10px 20px;
    border-radius: 6px;
    text-decoration: none;
    font-weight: 500;
    transition: background 0.2s;
}
.btn-mapa:hover {
    background: #0369a1;
    color: white !important;
}

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

/* Sticky CTA - Informe jurídico contextual (Quick Win #2 SEO 2026) */
.sticky-cta-subasta {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(255, 255, 255, 0.97);
    border-top: 2px solid #1e40af;
    padding: 12px 16px;
    z-index: 9999;
    box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
    display: none;
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
}
.sticky-cta-subasta.visible {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    animation: stickyCtaSlideUp 0.3s ease-out;
}
@keyframes stickyCtaSlideUp {
    from { transform: translateY(100%); opacity: 0; }
    to   { transform: translateY(0); opacity: 1; }
}
.sticky-cta-subasta__info {
    flex: 1;
    min-width: 0;
}
.sticky-cta-subasta__title {
    font-weight: 600;
    color: #1e40af;
    font-size: 0.95em;
    margin: 0 0 2px 0;
    line-height: 1.3;
}
.sticky-cta-subasta__meta {
    font-size: 0.8em;
    color: #6b7280;
    margin: 0;
    line-height: 1.3;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.sticky-cta-subasta__btn {
    display: inline-block;
    background: #1e40af;
    color: white !important;
    padding: 10px 18px;
    border-radius: 6px;
    text-decoration: none;
    font-weight: 600;
    font-size: 0.9em;
    white-space: nowrap;
    transition: background 0.2s;
}
.sticky-cta-subasta__btn:hover {
    background: #1e3a8a;
    color: white !important;
}
.sticky-cta-subasta__close {
    background: none;
    border: none;
    color: #6b7280;
    font-size: 1.4em;
    cursor: pointer;
    padding: 0 6px;
    line-height: 1;
    flex-shrink: 0;
}
.sticky-cta-subasta__close:hover {
    color: #1f2937;
}
@media (max-width: 640px) {
    .sticky-cta-subasta {
        padding: 10px 12px;
        gap: 8px;
    }
    .sticky-cta-subasta__title {
        font-size: 0.85em;
    }
    .sticky-cta-subasta__meta {
        font-size: 0.72em;
    }
    .sticky-cta-subasta__btn {
        padding: 9px 12px;
        font-size: 0.82em;
    }
    /* Padding inferior al body para no tapar contenido tras el footer */
    body.has-sticky-cta-subasta { padding-bottom: 80px; }
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
                    import urllib.parse

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

                    html += f"""
        <!-- Mapa de ubicación -->
        <div class="mapa-ubicacion">
            <h3>📍 Ubicación del Inmueble</h3>
            <div class="mapa-container">
                <iframe
                    src="https://www.google.com/maps?q={direccion_encoded}&output=embed"
                    width="100%"
                    height="350"
                    style="border:0; border-radius: 8px;"
                    allowfullscreen=""
                    loading="lazy"
                    referrerpolicy="no-referrer-when-downgrade">
                </iframe>
            </div>
            <p class="mapa-direccion"><strong>Dirección:</strong> {direccion_original}</p>
            <a href="https://www.google.com/maps/search/?api=1&query={direccion_encoded}"
               target="_blank"
               rel="nofollow"
               class="btn-mapa">
                🗺️ Ver en Google Maps
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
            html += f'            <li><a href="{subasta.url_edicto}" target="_blank" rel="nofollow">📜 Edicto de la Subasta (PDF)</a></li>\n'
        if subasta.url_certificacion_cargas:
            html += f'            <li><a href="{subasta.url_certificacion_cargas}" target="_blank" rel="nofollow">📋 Certificación de Cargas (PDF)</a></li>\n'

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

        # CTA - Llamada a la acción
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
        <a href="{self.contact_url}?subasta={urllib.parse.quote(subasta.id_subasta)}&tipo={urllib.parse.quote(tipo_bien)}&localidad={urllib.parse.quote(localidad)}&provincia={urllib.parse.quote(provincia)}&utm_source=ficha_body" class="btn-cta" title="Solicitar análisis gratuito de subasta en {localidad}">
            Solicitar Análisis Gratuito
        </a>
    </div>

    <!-- Enlace BOE -->
    <div class="subasta-enlace-boe">
        <p>
            <a href="{subasta.url_detalle or f'https://subastas.boe.es/detalleSubasta.php?idSub={subasta.id_subasta}'}"
               target="_blank" rel="nofollow">
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

<!-- Sticky CTA - Informe jurídico contextual (Quick Win #2 SEO 2026) -->
<aside class="sticky-cta-subasta" id="sticky-cta-subasta" role="complementary" aria-label="Solicitar informe jurídico de esta subasta">
    <div class="sticky-cta-subasta__info">
        <p class="sticky-cta-subasta__title">📄 Informe jurídico de ESTE activo · 72,60€ · 48h</p>
        <p class="sticky-cta-subasta__meta">{subasta.id_subasta} · {tipo_bien} en {localidad}</p>
    </div>
    <a href="{self.contact_url}?subasta={urllib.parse.quote(subasta.id_subasta)}&tipo={urllib.parse.quote(tipo_bien)}&localidad={urllib.parse.quote(localidad)}&provincia={urllib.parse.quote(provincia)}&utm_source=ficha_sticky#analisis"
       class="sticky-cta-subasta__btn"
       title="Solicitar informe jurídico de {tipo_bien} en {localidad}">
        Solicitar informe &rarr;
    </a>
    <button type="button" class="sticky-cta-subasta__close" aria-label="Cerrar" data-sticky-cta-close>&times;</button>
</aside>
"""
        html += STICKY_CTA_SCRIPT
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

    def _generate_meta(self, subasta: Subasta) -> dict:
        """
        Genera los campos meta para el post, incluyendo SEO.

        Incluye campos para:
        - Datos internos de la subasta
        - SEO (Yoast/Rank Math compatible)
        - Open Graph para redes sociales
        - Información de múltiples lotes
        """
        bien = subasta.get_bien_principal()

        # Meta description SEO
        meta_description = self._generate_meta_description(subasta)

        # Título SEO (puede ser ligeramente diferente al título del post)
        tipo = bien.subtipo_bien if bien and bien.subtipo_bien else "Inmueble"
        localidad = bien.localidad if bien and bien.localidad else "España"
        provincia = bien.provincia if bien and bien.provincia else ""

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

            # SEO - Yoast compatible
            "_yoast_wpseo_metadesc": meta_description,
            "_yoast_wpseo_focuskw": focus_keyword,
            "_yoast_wpseo_opengraph-title": og_title,
            "_yoast_wpseo_opengraph-description": meta_description,
            "_yoast_wpseo_twitter-title": og_title,
            "_yoast_wpseo_twitter-description": meta_description,

            # SEO - Rank Math compatible
            "rank_math_description": meta_description,
            "rank_math_focus_keyword": focus_keyword,
            "rank_math_title": seo_title,
            "rank_math_canonical_url": "",
            # Disable Rank Math auto-schema (we generate our own JSON-LD)
            "rank_math_rich_snippet": "off",
        }

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
