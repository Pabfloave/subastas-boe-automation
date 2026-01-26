"""
Publicador de subastas en WordPress.
Genera contenido HTML y publica posts usando el cliente WordPress.
"""
import logging
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
        # Verificar si ya existe
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
            # Actualizar post existente
            post_id = existing_post["id"]
            self.client.update_post(post_id, post_data)
            logger.info(f"Post actualizado: {post_id} - {subasta.id_subasta}")
            return post_id
        else:
            # Crear nuevo post
            result = self.client.create_post(**post_data)
            post_id = result["id"]
            logger.info(f"Post creado: {post_id} - {subasta.id_subasta}")
            return post_id

    def _find_existing_post(self, id_subasta: str) -> Optional[dict]:
        """Busca un post existente por ID de subasta."""
        return self.client.get_post_by_meta("_subasta_id", id_subasta)

    def _generate_title(self, subasta: Subasta) -> str:
        """Genera el título SEO-friendly del post."""
        bien = subasta.get_bien_principal()

        if bien:
            tipo = bien.subtipo_bien or "Inmueble"
            localidad = bien.localidad or "Andalucía"
            return f"Subasta {tipo} en {localidad}"
        else:
            return f"Subasta BOE {subasta.id_subasta}"

    def _generate_content(self, subasta: Subasta) -> str:
        """Genera el contenido HTML del post."""
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

        html = f"""
<div class="subasta-detalle">

    <!-- Alerta de Estado -->
    <div class="subasta-alerta {estado_class}">
        <strong>🔔 {estado_texto.upper()}</strong>
        {f' - Finaliza: {format_date(subasta.fecha_conclusion)}' if subasta.fecha_conclusion else ''}
    </div>

    <!-- Información General -->
    <div class="subasta-seccion">
        <h2>📋 Información de la Subasta</h2>
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

        # Sección de bienes
        if bien:
            html += f"""
    <!-- Datos del Inmueble -->
    <div class="subasta-seccion">
        <h2>🏠 Datos del Inmueble</h2>
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
                <td>{bien.provincia or 'Andalucía'}</td>
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
    <!-- Documentos -->
    <div class="subasta-seccion">
        <h2>📄 Documentos</h2>
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
        <h2>⚖️ Autoridad Gestora</h2>
        <p><strong>{subasta.autoridad_gestora or 'Juzgado'}</strong></p>
        <p>Localidad: {subasta.localidad_juzgado or 'No especificada'}</p>
"""
        if subasta.telefono_juzgado:
            html += f"        <p>Teléfono: {subasta.telefono_juzgado}</p>\n"
        if subasta.email_juzgado:
            html += f"        <p>Email: {subasta.email_juzgado}</p>\n"

        html += "    </div>\n"

        # CTA - Llamada a la acción
        html += f"""
    <!-- CTA -->
    <div class="subasta-cta">
        <h2>¿Interesado en esta subasta?</h2>
        <p>Nuestro equipo de abogados especializados puede ayudarte con todo el proceso:</p>
        <ul>
            <li>✅ Análisis de la documentación</li>
            <li>✅ Verificación de cargas</li>
            <li>✅ Asesoramiento legal completo</li>
            <li>✅ Gestión de la puja</li>
        </ul>
        <a href="{self.contact_url}" class="btn-cta">
            📞 Solicitar Análisis Gratuito
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

    def _generate_meta(self, subasta: Subasta) -> dict:
        """Genera los campos meta para el post."""
        bien = subasta.get_bien_principal()

        meta = {
            "_subasta_id": subasta.id_subasta,
            "_subasta_tipo": subasta.tipo_subasta or "",
            "_subasta_estado": subasta.estado or "",
            "_subasta_valor": str(subasta.valor_subasta),
            "_subasta_deposito": str(subasta.importe_deposito),
            "_subasta_fecha_inicio": subasta.fecha_inicio.isoformat() if subasta.fecha_inicio else "",
            "_subasta_fecha_fin": subasta.fecha_conclusion.isoformat() if subasta.fecha_conclusion else "",
        }

        if bien:
            meta.update({
                "_bien_tipo": bien.subtipo_bien or bien.tipo_bien or "",
                "_bien_direccion": bien.direccion or "",
                "_bien_localidad": bien.localidad or "",
                "_bien_provincia": bien.provincia or "",
                "_bien_cp": bien.codigo_postal or "",
            })

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
