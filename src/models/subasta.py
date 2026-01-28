"""
Modelos de datos para subastas y bienes inmuebles.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import hashlib
import json


@dataclass
class Bien:
    """Representa un bien inmueble en una subasta."""
    id: Optional[int] = None
    id_subasta: str = ""
    numero_bien: int = 1
    tipo_bien: str = "Inmueble"
    subtipo_bien: str = ""
    descripcion: str = ""
    direccion: str = ""
    codigo_postal: str = ""
    localidad: str = ""
    provincia: str = ""
    provincia_codigo: str = ""
    situacion_posesoria: str = ""
    visitable: str = ""
    cargas: str = ""
    valor_tasacion: Decimal = Decimal("0")
    fotos_urls: List[str] = field(default_factory=list)
    # Valores económicos específicos del lote
    valor_subasta_lote: Decimal = Decimal("0")
    importe_deposito_lote: Decimal = Decimal("0")
    puja_minima_lote: Decimal = Decimal("0")
    tramos_pujas_lote: Decimal = Decimal("0")

    def to_dict(self) -> dict:
        """Convierte el bien a diccionario."""
        return {
            "id": self.id,
            "id_subasta": self.id_subasta,
            "numero_bien": self.numero_bien,
            "tipo_bien": self.tipo_bien,
            "subtipo_bien": self.subtipo_bien,
            "descripcion": self.descripcion,
            "direccion": self.direccion,
            "codigo_postal": self.codigo_postal,
            "localidad": self.localidad,
            "provincia": self.provincia,
            "provincia_codigo": self.provincia_codigo,
            "situacion_posesoria": self.situacion_posesoria,
            "visitable": self.visitable,
            "cargas": self.cargas,
            "valor_tasacion": str(self.valor_tasacion),
            "fotos_urls": self.fotos_urls,
            "valor_subasta_lote": str(self.valor_subasta_lote),
            "importe_deposito_lote": str(self.importe_deposito_lote),
            "puja_minima_lote": str(self.puja_minima_lote),
            "tramos_pujas_lote": str(self.tramos_pujas_lote),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Bien":
        """Crea un Bien desde un diccionario."""
        return cls(
            id=data.get("id"),
            id_subasta=data.get("id_subasta", ""),
            numero_bien=data.get("numero_bien", 1),
            tipo_bien=data.get("tipo_bien", "Inmueble"),
            subtipo_bien=data.get("subtipo_bien", ""),
            descripcion=data.get("descripcion", ""),
            direccion=data.get("direccion", ""),
            codigo_postal=data.get("codigo_postal", ""),
            localidad=data.get("localidad", ""),
            provincia=data.get("provincia", ""),
            provincia_codigo=data.get("provincia_codigo", ""),
            situacion_posesoria=data.get("situacion_posesoria", ""),
            visitable=data.get("visitable", ""),
            cargas=data.get("cargas", ""),
            valor_tasacion=Decimal(data.get("valor_tasacion", "0")),
            fotos_urls=data.get("fotos_urls", []),
            valor_subasta_lote=Decimal(data.get("valor_subasta_lote", "0")),
            importe_deposito_lote=Decimal(data.get("importe_deposito_lote", "0")),
            puja_minima_lote=Decimal(data.get("puja_minima_lote", "0")),
            tramos_pujas_lote=Decimal(data.get("tramos_pujas_lote", "0")),
        )


@dataclass
class Subasta:
    """Representa una subasta del BOE."""
    id: Optional[int] = None
    id_subasta: str = ""  # SUB-JA-2025-249514
    tipo_subasta: str = ""  # JUDICIAL EN VIA DE APREMIO
    estado: str = ""  # Celebrándose, Próxima apertura, etc.
    cuenta_expediente: str = ""
    fecha_inicio: Optional[datetime] = None
    fecha_conclusion: Optional[datetime] = None
    cantidad_reclamada: Decimal = Decimal("0")
    valor_subasta: Decimal = Decimal("0")
    tasacion: Decimal = Decimal("0")
    puja_minima: Decimal = Decimal("0")
    tramos_pujas: Decimal = Decimal("0")
    importe_deposito: Decimal = Decimal("0")
    anuncio_boe: str = ""  # BOE-B-2026-1284
    lotes: str = ""
    url_detalle: str = ""
    url_edicto: str = ""
    url_certificacion_cargas: str = ""
    autoridad_gestora: str = ""
    localidad_juzgado: str = ""
    telefono_juzgado: str = ""
    fax_juzgado: str = ""
    email_juzgado: str = ""
    fecha_scraping: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None
    publicado_wp: bool = False
    wp_post_id: Optional[int] = None
    hash_datos: str = ""
    activa: bool = True
    bienes: List[Bien] = field(default_factory=list)

    def calcular_hash(self) -> str:
        """Calcula un hash de los datos principales para detectar cambios."""
        datos = {
            "id_subasta": self.id_subasta,
            "estado": self.estado,
            "valor_subasta": str(self.valor_subasta),
            "fecha_conclusion": self.fecha_conclusion.isoformat() if self.fecha_conclusion else "",
            "bienes_count": len(self.bienes),
        }
        data_str = json.dumps(datos, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Convierte la subasta a diccionario."""
        return {
            "id": self.id,
            "id_subasta": self.id_subasta,
            "tipo_subasta": self.tipo_subasta,
            "estado": self.estado,
            "cuenta_expediente": self.cuenta_expediente,
            "fecha_inicio": self.fecha_inicio.isoformat() if self.fecha_inicio else None,
            "fecha_conclusion": self.fecha_conclusion.isoformat() if self.fecha_conclusion else None,
            "cantidad_reclamada": str(self.cantidad_reclamada),
            "valor_subasta": str(self.valor_subasta),
            "tasacion": str(self.tasacion),
            "puja_minima": str(self.puja_minima),
            "tramos_pujas": str(self.tramos_pujas),
            "importe_deposito": str(self.importe_deposito),
            "anuncio_boe": self.anuncio_boe,
            "lotes": self.lotes,
            "url_detalle": self.url_detalle,
            "url_edicto": self.url_edicto,
            "url_certificacion_cargas": self.url_certificacion_cargas,
            "autoridad_gestora": self.autoridad_gestora,
            "localidad_juzgado": self.localidad_juzgado,
            "telefono_juzgado": self.telefono_juzgado,
            "fax_juzgado": self.fax_juzgado,
            "email_juzgado": self.email_juzgado,
            "fecha_scraping": self.fecha_scraping.isoformat() if self.fecha_scraping else None,
            "fecha_actualizacion": self.fecha_actualizacion.isoformat() if self.fecha_actualizacion else None,
            "publicado_wp": self.publicado_wp,
            "wp_post_id": self.wp_post_id,
            "hash_datos": self.hash_datos,
            "activa": self.activa,
            "bienes": [b.to_dict() for b in self.bienes],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Subasta":
        """Crea una Subasta desde un diccionario."""
        def parse_datetime(val):
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(val)

        bienes_data = data.get("bienes", [])
        bienes = [Bien.from_dict(b) if isinstance(b, dict) else b for b in bienes_data]

        return cls(
            id=data.get("id"),
            id_subasta=data.get("id_subasta", ""),
            tipo_subasta=data.get("tipo_subasta", ""),
            estado=data.get("estado", ""),
            cuenta_expediente=data.get("cuenta_expediente", ""),
            fecha_inicio=parse_datetime(data.get("fecha_inicio")),
            fecha_conclusion=parse_datetime(data.get("fecha_conclusion")),
            cantidad_reclamada=Decimal(data.get("cantidad_reclamada", "0")),
            valor_subasta=Decimal(data.get("valor_subasta", "0")),
            tasacion=Decimal(data.get("tasacion", "0")),
            puja_minima=Decimal(data.get("puja_minima", "0")),
            tramos_pujas=Decimal(data.get("tramos_pujas", "0")),
            importe_deposito=Decimal(data.get("importe_deposito", "0")),
            anuncio_boe=data.get("anuncio_boe", ""),
            lotes=data.get("lotes", ""),
            url_detalle=data.get("url_detalle", ""),
            url_edicto=data.get("url_edicto", ""),
            url_certificacion_cargas=data.get("url_certificacion_cargas", ""),
            autoridad_gestora=data.get("autoridad_gestora", ""),
            localidad_juzgado=data.get("localidad_juzgado", ""),
            telefono_juzgado=data.get("telefono_juzgado", ""),
            fax_juzgado=data.get("fax_juzgado", ""),
            email_juzgado=data.get("email_juzgado", ""),
            fecha_scraping=parse_datetime(data.get("fecha_scraping")),
            fecha_actualizacion=parse_datetime(data.get("fecha_actualizacion")),
            publicado_wp=data.get("publicado_wp", False),
            wp_post_id=data.get("wp_post_id"),
            hash_datos=data.get("hash_datos", ""),
            activa=data.get("activa", True),
            bienes=bienes,
        )

    def get_bien_principal(self) -> Optional[Bien]:
        """Obtiene el primer bien de la subasta."""
        return self.bienes[0] if self.bienes else None

    def get_titulo_seo(self) -> str:
        """Genera un título SEO-friendly para la subasta."""
        bien = self.get_bien_principal()
        if bien:
            tipo = bien.subtipo_bien or "Inmueble"
            localidad = bien.localidad or "Andalucía"
            return f"Subasta {tipo} en {localidad} - {self.id_subasta}"
        return f"Subasta {self.id_subasta}"
