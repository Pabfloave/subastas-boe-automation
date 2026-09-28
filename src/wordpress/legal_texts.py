"""Textos jurídicos compartidos por fichas (publisher.py) y páginas de
provincia (page_generator.py).

Fuente única: antes cada generador tenía su propia versión y se contradecían
(las fichas hablaban de un depósito del 5 % y las provincias del 20 %). Tras la
LO 1/2025 conviven dos regímenes según la fecha de la demanda ejecutiva, y la
web debe explicarlo igual en todas partes — tanto por rigor jurídico como
porque buscadores y motores de IA penalizan las afirmaciones contradictorias.
"""
from __future__ import annotations

from typing import Optional

from config import settings

REFORMA_NORMA = "LO 1/2025"
REFORMA_VIGOR = "3 de abril de 2025"

# Depósito para pujar en subastas judiciales de inmuebles (art. 669.1 LEC).
DEPOSITO_JUDICIAL = (
    "En las subastas judiciales de inmuebles cuya demanda ejecutiva se presentó "
    f"a partir del {REFORMA_VIGOR}, el depósito es del 20 % del valor de subasta "
    "del bien, con un mínimo de 1.000 € (art. 669 LEC, en la redacción de la "
    f"{REFORMA_NORMA}); en los procedimientos iniciados antes se mantiene el 5 %. "
    "El Letrado de la Administración de Justicia puede elevar o reducir ese "
    "porcentaje, por lo que el importe exacto es el que figura en el anuncio "
    "del Portal de Subastas."
)

# Plazo del mejor postor para consignar el resto del precio (art. 670.1 LEC).
PLAZO_PAGO_JUDICIAL = (
    "En las subastas judiciales de inmuebles, el mejor postor dispone de 20 días "
    "desde el cierre de la subasta para consignar el resto del precio "
    f"(art. 670.1 LEC, tras la {REFORMA_NORMA}); en los procedimientos iniciados "
    f"antes del {REFORMA_VIGOR} el plazo es de 40 días."
)

# Duración del periodo de pujas en el Portal (art. 649 LEC).
PERIODO_PUJAS = "La subasta electrónica admite pujas durante 20 días naturales desde su apertura."

# Versión corta para tarjetas y listados.
DEPOSITO_RESUMEN = (
    f"20 % del valor de subasta (mín. 1.000 €) si la ejecución se inició desde el "
    f"{REFORMA_VIGOR}; 5 % en procedimientos anteriores."
)


def etiqueta_tipo(id_subasta: Optional[str], tipo_subasta: Optional[str] = None) -> str:
    """Complemento para "subasta …": "judicial", "notarial", "de la Agencia
    Tributaria", "de recaudación tributaria" o "administrativa".

    Un tercio de las subastas publicadas no son judiciales (AEAT, recaudación,
    notariales); presentarlas todas como "subasta judicial" es inexacto.
    """
    ident = (id_subasta or "").upper()
    tipo = (tipo_subasta or "").lower()
    if "judicial" in tipo or ident.startswith("SUB-J"):
        return "judicial"
    if "notarial" in tipo or ident.startswith("SUB-N"):
        return "notarial"
    if "agencia tributaria" in tipo or ident.startswith("SUB-AT"):
        return "de la Agencia Tributaria"
    if "recaudaci" in tipo or ident.startswith("SUB-RC"):
        return "de recaudación tributaria"
    return "administrativa"


def es_subasta_judicial(id_subasta: Optional[str], tipo_subasta: Optional[str] = None) -> bool:
    """True si la subasta es judicial (identificador SUB-J… o tipo "JUDICIAL").

    Las subastas de la AEAT (SUB-AT…), notariales y de otras administraciones
    tienen reglas de depósito y pago propias: para ellas no se afirma el régimen
    de la LEC y se remite al anuncio.
    """
    if tipo_subasta and "judicial" in tipo_subasta.lower():
        return True
    return bool(id_subasta) and id_subasta.upper().startswith("SUB-J")


def responsable_juridico() -> str:
    """Devuelve "Nombre (colegiado n.º X del Colegio Y)" ('' si no está configurado)."""
    if not settings.AUTOR_NOMBRE:
        return ""
    colegiacion = ""
    if settings.AUTOR_COLEGIADO:
        colegiacion = f"colegiado n.º {settings.AUTOR_COLEGIADO}"
    if settings.AUTOR_COLEGIO:
        colegiacion += (" del " if colegiacion else "") + settings.AUTOR_COLEGIO
    return f"{settings.AUTOR_NOMBRE} ({colegiacion})" if colegiacion else settings.AUTOR_NOMBRE


def autor_schema() -> Optional[dict]:
    """Person JSON-LD del responsable jurídico (con colegiación verificable)."""
    if not settings.AUTOR_NOMBRE:
        return None
    person = {"@type": "Person", "name": settings.AUTOR_NOMBRE, "jobTitle": "Abogado"}
    if settings.AUTOR_COLEGIO:
        colegio = {"@type": "Organization", "name": settings.AUTOR_COLEGIO}
        person["memberOf"] = colegio
        credential = {
            "@type": "EducationalOccupationalCredential",
            "credentialCategory": "Colegiación profesional de abogado",
            "recognizedBy": colegio,
        }
        if settings.AUTOR_COLEGIADO:
            credential["identifier"] = settings.AUTOR_COLEGIADO
        person["hasCredential"] = credential
    return person
