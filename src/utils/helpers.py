"""
Funciones auxiliares para el proyecto.
"""
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from typing import Optional


def format_currency(value: Decimal, symbol: str = "€") -> str:
    """
    Formatea un valor decimal como moneda.

    Args:
        value: Valor a formatear
        symbol: Símbolo de moneda

    Returns:
        String formateado (ej: "1.234,56 €")
    """
    try:
        num = float(value)
        # Formato español: punto como separador de miles, coma como decimal
        formatted = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{formatted} {symbol}"
    except (ValueError, TypeError):
        return f"0,00 {symbol}"


def format_date(dt: Optional[datetime], include_time: bool = True) -> str:
    """
    Formatea una fecha/hora.

    Args:
        dt: Fecha a formatear
        include_time: Si incluir la hora

    Returns:
        String formateado
    """
    if not dt:
        return "No disponible"

    if include_time:
        return dt.strftime("%d/%m/%Y a las %H:%M")
    else:
        return dt.strftime("%d/%m/%Y")


def generate_slug(text: str, max_length: int = 60) -> str:
    """
    Genera un slug SEO-friendly desde un texto.

    Args:
        text: Texto original
        max_length: Longitud máxima del slug

    Returns:
        Slug normalizado
    """
    if not text:
        return ""

    # Normalizar unicode (quitar acentos)
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ASCII', 'ignore').decode('ASCII')

    # Convertir a minúsculas
    text = text.lower()

    # Reemplazar espacios y caracteres especiales por guiones
    text = re.sub(r'[^a-z0-9]+', '-', text)

    # Eliminar guiones múltiples
    text = re.sub(r'-+', '-', text)

    # Eliminar guiones al inicio y final
    text = text.strip('-')

    # Truncar si es necesario
    if len(text) > max_length:
        text = text[:max_length].rsplit('-', 1)[0]

    return text


def clean_text(text: str) -> str:
    """
    Limpia un texto de espacios extra y caracteres especiales.

    Args:
        text: Texto a limpiar

    Returns:
        Texto limpio
    """
    if not text:
        return ""

    # Reemplazar múltiples espacios por uno solo
    text = re.sub(r'\s+', ' ', text)

    # Eliminar espacios al inicio y final
    text = text.strip()

    return text


def parse_spanish_number(text: str) -> Decimal:
    """
    Parsea un número en formato español a Decimal.

    Args:
        text: Texto con número (ej: "1.234,56 €")

    Returns:
        Decimal
    """
    if not text:
        return Decimal("0")

    # Eliminar todo excepto dígitos, comas y puntos
    cleaned = re.sub(r'[^\d,.-]', '', text)

    if not cleaned:
        return Decimal("0")

    try:
        # Determinar formato (español o inglés)
        if ',' in cleaned and '.' in cleaned:
            if cleaned.rfind(',') > cleaned.rfind('.'):
                # Formato español: 1.234,56
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # Formato inglés: 1,234.56
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            # Solo coma: probablemente decimal español
            cleaned = cleaned.replace(',', '.')

        return Decimal(cleaned)
    except:
        return Decimal("0")


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """
    Trunca un texto a una longitud máxima.

    Args:
        text: Texto a truncar
        max_length: Longitud máxima
        suffix: Sufijo a añadir si se trunca

    Returns:
        Texto truncado
    """
    if not text or len(text) <= max_length:
        return text or ""

    # Intentar cortar en un espacio
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')

    if last_space > max_length // 2:
        truncated = truncated[:last_space]

    return truncated + suffix


def extract_postal_code(text: str) -> Optional[str]:
    """
    Extrae un código postal español de un texto.

    Args:
        text: Texto que puede contener código postal

    Returns:
        Código postal o None
    """
    if not text:
        return None

    # Buscar patrón de código postal español (5 dígitos)
    match = re.search(r'\b(\d{5})\b', text)
    if match:
        return match.group(1)

    return None


def is_valid_subasta_id(id_subasta: str) -> bool:
    """
    Verifica si un ID de subasta tiene formato válido.

    Args:
        id_subasta: ID a verificar

    Returns:
        True si es válido
    """
    if not id_subasta:
        return False

    # Formato típico: SUB-XX-YYYY-NNNNNN
    pattern = r'^SUB-[A-Z]{2}-\d{4}-\d+$'
    return bool(re.match(pattern, id_subasta))


def get_provincia_from_cp(codigo_postal: str) -> Optional[str]:
    """
    Obtiene el código de provincia desde el código postal.

    Args:
        codigo_postal: Código postal (5 dígitos)

    Returns:
        Código de provincia (2 dígitos) o None
    """
    if not codigo_postal or len(codigo_postal) != 5:
        return None

    return codigo_postal[:2]


def format_address(
    direccion: str = None,
    localidad: str = None,
    provincia: str = None,
    codigo_postal: str = None
) -> str:
    """
    Formatea una dirección completa.

    Args:
        direccion: Calle y número
        localidad: Ciudad/pueblo
        provincia: Provincia
        codigo_postal: Código postal

    Returns:
        Dirección formateada
    """
    parts = []

    if direccion:
        parts.append(direccion)

    location_parts = []
    if codigo_postal:
        location_parts.append(codigo_postal)
    if localidad:
        location_parts.append(localidad)
    if provincia:
        location_parts.append(f"({provincia})")

    if location_parts:
        parts.append(" ".join(location_parts))

    return ", ".join(parts) if parts else "Dirección no disponible"


def calculate_percentage(part: Decimal, total: Decimal) -> float:
    """
    Calcula el porcentaje.

    Args:
        part: Parte
        total: Total

    Returns:
        Porcentaje (0-100)
    """
    try:
        if total == 0:
            return 0.0
        return float((part / total) * 100)
    except:
        return 0.0
