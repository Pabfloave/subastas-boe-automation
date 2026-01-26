"""
Parser para extraer datos estructurados del HTML del BOE.
"""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

from ..models.subasta import Subasta, Bien


class SubastaParser:
    """Parser para extraer datos de subastas del HTML del BOE."""

    @staticmethod
    def parse_listado(html: str) -> List[Dict]:
        """
        Parsea la página de listado de subastas y extrae información básica.

        Returns:
            Lista de diccionarios con información básica de cada subasta
        """
        soup = BeautifulSoup(html, "lxml")
        subastas = []

        # Buscar filas de resultados
        rows = soup.select("div.resultado-busqueda")
        if not rows:
            # Intentar otro selector
            rows = soup.select("table.resultado-busqueda tr")

        for row in rows:
            try:
                subasta_info = SubastaParser._parse_row_listado(row)
                if subasta_info and subasta_info.get("id_subasta"):
                    subastas.append(subasta_info)
            except Exception:
                continue

        return subastas

    @staticmethod
    def _parse_row_listado(row) -> Optional[Dict]:
        """Parsea una fila del listado de subastas."""
        info = {}

        # Buscar enlace con ID de subasta
        link = row.select_one("a[href*='idSub=']")
        if link:
            href = link.get("href", "")
            match = re.search(r"idSub=([A-Z0-9-]+)", href)
            if match:
                info["id_subasta"] = match.group(1)
                info["url_detalle"] = f"https://subastas.boe.es/detalleSubasta.php?idSub={info['id_subasta']}"

        # Buscar estado
        estado_elem = row.select_one(".estado-subasta, span.estado")
        if estado_elem:
            info["estado"] = estado_elem.get_text(strip=True)

        # Buscar valor
        valor_elem = row.select_one(".valor-subasta, td.valor")
        if valor_elem:
            info["valor_texto"] = valor_elem.get_text(strip=True)

        return info if info.get("id_subasta") else None

    @staticmethod
    def parse_detalle_general(html: str) -> Dict:
        """
        Parsea la pestaña de información general (ver=1).

        Returns:
            Diccionario con datos generales de la subasta
        """
        soup = BeautifulSoup(html, "lxml")
        datos = {}

        # Buscar tabla de datos o divs con información
        # El BOE usa diferentes estructuras, intentamos varias

        # Método 1: Buscar por labels específicos
        label_mapping = {
            "Identificador": "id_subasta",
            "Tipo de subasta": "tipo_subasta",
            "Estado": "estado",
            "Fecha de inicio": "fecha_inicio",
            "Fecha de conclusión": "fecha_conclusion",
            "Cantidad reclamada": "cantidad_reclamada",
            "Valor subasta": "valor_subasta",
            "Tasación": "tasacion",
            "Puja mínima": "puja_minima",
            "Tramos entre pujas": "tramos_pujas",
            "Importe del depósito": "importe_deposito",
            "Anuncio BOE": "anuncio_boe",
            "Lotes": "lotes",
        }

        # Buscar en estructura de tabla
        for row in soup.select("tr, div.fila-datos"):
            cells = row.select("td, th, div.campo")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).rstrip(":")
                value = cells[1].get_text(strip=True)

                for key_label, field_name in label_mapping.items():
                    if key_label.lower() in label.lower():
                        datos[field_name] = value
                        break

        # Buscar enlaces a documentos
        for link in soup.select("a[href*='.pdf'], a[href*='documento']"):
            href = link.get("href", "")
            text = link.get_text(strip=True).lower()

            if "edicto" in text:
                datos["url_edicto"] = SubastaParser._make_absolute_url(href)
            elif "carga" in text or "certificación" in text:
                datos["url_certificacion_cargas"] = SubastaParser._make_absolute_url(href)

        return datos

    @staticmethod
    def parse_detalle_bienes(html: str, id_subasta: str) -> List[Bien]:
        """
        Parsea la pestaña de bienes (ver=3).

        Returns:
            Lista de objetos Bien
        """
        soup = BeautifulSoup(html, "lxml")
        bienes = []

        # Buscar secciones de bienes
        bien_sections = soup.select("div.bien, div.lote, section.bien")
        if not bien_sections:
            # Intentar con toda la página si no hay secciones específicas
            bien_sections = [soup]

        for idx, section in enumerate(bien_sections, 1):
            bien = SubastaParser._parse_bien_section(section, id_subasta, idx)
            if bien:
                bienes.append(bien)

        return bienes

    @staticmethod
    def _parse_bien_section(section, id_subasta: str, numero: int) -> Optional[Bien]:
        """Parsea una sección de bien inmueble."""
        bien = Bien(
            id_subasta=id_subasta,
            numero_bien=numero,
            tipo_bien="Inmueble",
        )

        # Mapeo de campos
        field_mapping = {
            "Descripción": "descripcion",
            "Dirección": "direccion",
            "Código postal": "codigo_postal",
            "Código Postal": "codigo_postal",
            "Localidad": "localidad",
            "Provincia": "provincia",
            "Situación posesoria": "situacion_posesoria",
            "Visitable": "visitable",
            "Cargas": "cargas",
            "Valor de tasación": "valor_tasacion",
            "Valoración": "valor_tasacion",
        }

        # Extraer campos de la sección
        for row in section.select("tr, div.fila, dl"):
            # Intentar extraer par label-valor
            label_elem = row.select_one("th, dt, .label, .campo-label")
            value_elem = row.select_one("td, dd, .valor, .campo-valor")

            if label_elem and value_elem:
                label = label_elem.get_text(strip=True).rstrip(":")
                value = value_elem.get_text(strip=True)

                for key_label, field_name in field_mapping.items():
                    if key_label.lower() in label.lower():
                        if field_name == "valor_tasacion":
                            bien.valor_tasacion = SubastaParser._parse_decimal(value)
                        else:
                            setattr(bien, field_name, value)
                        break

        # Buscar tipo/subtipo de bien
        subtipo_elem = section.select_one(".tipo-bien, .subtipo")
        if subtipo_elem:
            bien.subtipo_bien = subtipo_elem.get_text(strip=True)
        else:
            # Inferir subtipo de la descripción
            bien.subtipo_bien = SubastaParser._inferir_subtipo(bien.descripcion)

        # Buscar fotos
        fotos = []
        for img in section.select("img[src*='foto'], img[src*='imagen'], a[href*='.jpg'], a[href*='.png']"):
            src = img.get("src") or img.get("href")
            if src:
                fotos.append(SubastaParser._make_absolute_url(src))
        bien.fotos_urls = fotos

        # Extraer código de provincia si no está presente
        if bien.provincia and not bien.provincia_codigo:
            bien.provincia_codigo = SubastaParser._get_codigo_provincia(bien.provincia)

        return bien if bien.direccion or bien.descripcion else None

    @staticmethod
    def parse_autoridad_gestora(html: str) -> Dict:
        """
        Parsea la pestaña de autoridad gestora (ver=2).

        Returns:
            Diccionario con datos de la autoridad gestora
        """
        soup = BeautifulSoup(html, "lxml")
        datos = {}

        field_mapping = {
            "Autoridad": "autoridad_gestora",
            "Juzgado": "autoridad_gestora",
            "Localidad": "localidad_juzgado",
            "Teléfono": "telefono_juzgado",
            "Fax": "fax_juzgado",
            "Email": "email_juzgado",
            "Correo": "email_juzgado",
        }

        for row in soup.select("tr, div.fila"):
            cells = row.select("td, th, div.campo")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).rstrip(":")
                value = cells[1].get_text(strip=True)

                for key_label, field_name in field_mapping.items():
                    if key_label.lower() in label.lower():
                        datos[field_name] = value
                        break

        return datos

    @staticmethod
    def _parse_decimal(value: str) -> Decimal:
        """Convierte un string de valor monetario a Decimal."""
        if not value:
            return Decimal("0")

        try:
            # Limpiar el string: quitar símbolos, espacios, EUR, etc.
            cleaned = re.sub(r"[^\d,.-]", "", value)
            # Manejar formato español (1.234,56) vs inglés (1,234.56)
            if "," in cleaned and "." in cleaned:
                if cleaned.rfind(",") > cleaned.rfind("."):
                    # Formato español: 1.234,56
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                else:
                    # Formato inglés: 1,234.56
                    cleaned = cleaned.replace(",", "")
            elif "," in cleaned:
                # Solo coma, probablemente decimal español
                cleaned = cleaned.replace(",", ".")

            return Decimal(cleaned) if cleaned else Decimal("0")
        except InvalidOperation:
            return Decimal("0")

    @staticmethod
    def _parse_datetime(value: str) -> Optional[datetime]:
        """Convierte un string de fecha a datetime."""
        if not value:
            return None

        # Limpiar el valor: quitar zona horaria y formato ISO adicional
        # Formato BOE: "23-01-2026 18:00:00 CET  (ISO: 2026-01-23T18:00:00+01:00)"
        cleaned = value.strip()

        # Quitar todo después de CET, CEST, o (ISO
        for separator in [' CET', ' CEST', '(ISO', ' (']:
            if separator in cleaned:
                cleaned = cleaned.split(separator)[0].strip()

        # Formatos comunes del BOE
        formatos = [
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d-%m-%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in formatos:
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue

        return None

    @staticmethod
    def _make_absolute_url(url: str) -> str:
        """Convierte una URL relativa a absoluta."""
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return f"https://subastas.boe.es{url}"
        return f"https://subastas.boe.es/{url}"

    @staticmethod
    def _inferir_subtipo(descripcion: str) -> str:
        """Infiere el subtipo de inmueble desde la descripción."""
        desc_lower = descripcion.lower() if descripcion else ""

        if "vivienda" in desc_lower or "piso" in desc_lower or "apartamento" in desc_lower:
            return "Vivienda"
        elif "local" in desc_lower or "comercial" in desc_lower:
            return "Local comercial"
        elif "garaje" in desc_lower or "parking" in desc_lower or "aparcamiento" in desc_lower:
            return "Garaje"
        elif "trastero" in desc_lower:
            return "Trastero"
        elif "nave" in desc_lower or "industrial" in desc_lower:
            return "Nave industrial"
        elif "finca" in desc_lower or "rústica" in desc_lower or "rustica" in desc_lower:
            return "Finca rústica"
        elif "solar" in desc_lower or "terreno" in desc_lower:
            return "Solar"
        else:
            return "Inmueble"

    @staticmethod
    def _get_codigo_provincia(nombre_provincia: str) -> str:
        """Obtiene el código de provincia desde el nombre."""
        provincias = {
            "almería": "04", "almeria": "04",
            "cádiz": "11", "cadiz": "11",
            "córdoba": "14", "cordoba": "14",
            "granada": "18",
            "huelva": "21",
            "jaén": "23", "jaen": "23",
            "málaga": "29", "malaga": "29",
            "sevilla": "41",
        }
        return provincias.get(nombre_provincia.lower().strip(), "")

    @staticmethod
    def _inferir_estado(fecha_inicio: Optional[datetime], fecha_conclusion: Optional[datetime]) -> str:
        """Infiere el estado de la subasta a partir de las fechas."""
        now = datetime.now()

        if fecha_inicio and fecha_conclusion:
            if now < fecha_inicio:
                return "Próxima"
            elif now > fecha_conclusion:
                return "Finalizada"
            else:
                return "Celebrándose"
        elif fecha_inicio and now >= fecha_inicio:
            return "Celebrándose"
        elif fecha_conclusion and now > fecha_conclusion:
            return "Finalizada"

        return "En curso"

    @staticmethod
    def crear_subasta_desde_detalle(
        datos_generales: Dict,
        bienes: List[Bien],
        datos_autoridad: Dict
    ) -> Subasta:
        """
        Crea un objeto Subasta completo desde los datos parseados.
        """
        # Parsear fechas primero
        fecha_inicio = SubastaParser._parse_datetime(datos_generales.get("fecha_inicio", ""))
        fecha_conclusion = SubastaParser._parse_datetime(datos_generales.get("fecha_conclusion", ""))

        # Inferir estado si no está presente
        estado = datos_generales.get("estado", "")
        if not estado:
            estado = SubastaParser._inferir_estado(fecha_inicio, fecha_conclusion)

        subasta = Subasta(
            id_subasta=datos_generales.get("id_subasta", ""),
            tipo_subasta=datos_generales.get("tipo_subasta", ""),
            estado=estado,
            cuenta_expediente=datos_generales.get("cuenta_expediente", ""),
            fecha_inicio=fecha_inicio,
            fecha_conclusion=fecha_conclusion,
            cantidad_reclamada=SubastaParser._parse_decimal(datos_generales.get("cantidad_reclamada", "")),
            valor_subasta=SubastaParser._parse_decimal(datos_generales.get("valor_subasta", "")),
            tasacion=SubastaParser._parse_decimal(datos_generales.get("tasacion", "")),
            puja_minima=SubastaParser._parse_decimal(datos_generales.get("puja_minima", "")),
            tramos_pujas=SubastaParser._parse_decimal(datos_generales.get("tramos_pujas", "")),
            importe_deposito=SubastaParser._parse_decimal(datos_generales.get("importe_deposito", "")),
            anuncio_boe=datos_generales.get("anuncio_boe", ""),
            lotes=datos_generales.get("lotes", ""),
            url_detalle=datos_generales.get("url_detalle", ""),
            url_edicto=datos_generales.get("url_edicto", ""),
            url_certificacion_cargas=datos_generales.get("url_certificacion_cargas", ""),
            autoridad_gestora=datos_autoridad.get("autoridad_gestora", ""),
            localidad_juzgado=datos_autoridad.get("localidad_juzgado", ""),
            telefono_juzgado=datos_autoridad.get("telefono_juzgado", ""),
            fax_juzgado=datos_autoridad.get("fax_juzgado", ""),
            email_juzgado=datos_autoridad.get("email_juzgado", ""),
            bienes=bienes,
        )

        return subasta
