"""
Geocodificación de direcciones de subastas BOE usando Google Geocoding API,
con cache persistente en SQLite (tabla geocode_cache).

El cache es clave para:
- Evitar pagar lookups repetidos (las direcciones se reusan al re-publicar).
- Acelerar la publicación.
- Cachear también los fallos (status='failed') para no reintentar direcciones intratables.
"""
import hashlib
import logging
import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import settings

logger = logging.getLogger(__name__)


GEOCODE_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json"
REQUEST_TIMEOUT = 10
# Google permite 50 req/s para Geocoding; con un sleep mínimo evitamos bursting accidental.
MIN_INTERVAL_BETWEEN_REQUESTS = 0.05


@dataclass
class GeocodeResult:
    """Resultado de geocodificación. lat/lng son None si la geocodificación falló."""
    lat: Optional[float]
    lng: Optional[float]
    status: str  # 'ok' o 'failed'
    formatted_address: Optional[str] = None
    cached: bool = False

    @property
    def ok(self) -> bool:
        return self.status == "ok" and self.lat is not None and self.lng is not None


def _normalize(s: Optional[str]) -> str:
    """Normaliza para hashing: minúsculas, sin acentos, sin espacios extra."""
    if not s:
        return ""
    s = s.strip().lower()
    # Quitar diacríticos
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s)
    return s


def _hash_address(direccion: str, localidad: str, provincia: str, cp: str) -> str:
    """SHA256 de la concatenación normalizada de los campos."""
    key = "|".join([
        _normalize(direccion),
        _normalize(localidad),
        _normalize(provincia),
        _normalize(cp),
    ])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _build_query(direccion: str, localidad: str, provincia: str, cp: str) -> str:
    """Construye la query enviada a Google. Filtra basura tipo 's/n', desconocido, etc."""
    partes = []
    if direccion:
        d = direccion.strip()
        # Quitar marcadores genéricos que Google interpreta literal
        d = re.sub(r"\bs\s*/\s*n\b\.?", "", d, flags=re.IGNORECASE)
        d = re.sub(r"\b(sin\s+n[uú]mero)\b", "", d, flags=re.IGNORECASE)
        d = re.sub(r"\s+,", ",", d).strip(" ,")
        if d:
            partes.append(d)
    if localidad:
        partes.append(localidad.strip())
    if provincia:
        # BOE usa nombres bilingües "Valencia/València"; quedamos con el primer token.
        prov = provincia.split("/")[0].strip()
        if prov:
            partes.append(prov)
    if cp:
        partes.append(cp.strip())
    partes.append("España")
    return ", ".join(p for p in partes if p)


class Geocoder:
    """Geocodificador con cache SQLite. Thread-unsafe — usar uno por proceso."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = REQUEST_TIMEOUT,
    ):
        self.db_path = db_path or settings.DB_PATH
        self.api_key = api_key if api_key is not None else settings.GOOGLE_MAPS_API_KEY
        self.timeout = timeout
        self._last_request_at = 0.0
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self):
        """Crea la tabla si no existe (idempotente; Database._create_tables también la crea)."""
        conn = self._connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS geocode_cache (
                    direccion_hash TEXT PRIMARY KEY,
                    direccion_raw TEXT NOT NULL,
                    lat REAL,
                    lng REAL,
                    status TEXT NOT NULL,
                    formatted_address TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_geocode_status ON geocode_cache(status)"
            )
            conn.commit()
        finally:
            conn.close()

    def _cache_get(self, direccion_hash: str) -> Optional[GeocodeResult]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT lat, lng, status, formatted_address FROM geocode_cache WHERE direccion_hash = ?",
                (direccion_hash,),
            ).fetchone()
            if not row:
                return None
            return GeocodeResult(
                lat=row["lat"],
                lng=row["lng"],
                status=row["status"],
                formatted_address=row["formatted_address"],
                cached=True,
            )
        finally:
            conn.close()

    def _cache_put(self, direccion_hash: str, direccion_raw: str, result: GeocodeResult):
        conn = self._connect()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO geocode_cache
                    (direccion_hash, direccion_raw, lat, lng, status, formatted_address)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                direccion_hash,
                direccion_raw,
                result.lat,
                result.lng,
                result.status,
                result.formatted_address,
            ))
            conn.commit()
        finally:
            conn.close()

    def _throttle(self):
        elapsed = time.time() - self._last_request_at
        if elapsed < MIN_INTERVAL_BETWEEN_REQUESTS:
            time.sleep(MIN_INTERVAL_BETWEEN_REQUESTS - elapsed)
        self._last_request_at = time.time()

    def _call_google(self, query: str) -> GeocodeResult:
        """Llama a Google Geocoding API. Devuelve GeocodeResult (ok/failed/error_no_cache)."""
        if not self.api_key:
            # error_no_cache evita persistir el fallo: cuando el usuario configure la key,
            # las próximas llamadas reintentarán en lugar de servir 'failed' del cache.
            logger.debug("GOOGLE_MAPS_API_KEY no configurada; geocoding deshabilitado")
            return GeocodeResult(lat=None, lng=None, status="error_no_cache")

        self._throttle()
        params = {
            "address": query,
            "key": self.api_key,
            "region": "es",
            "language": "es",
        }
        try:
            resp = requests.get(GEOCODE_ENDPOINT, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.warning("Geocoding HTTP error para %r: %s", query, exc)
            return GeocodeResult(lat=None, lng=None, status="failed")

        status = data.get("status")
        # OVER_QUERY_LIMIT / REQUEST_DENIED son fallos de configuración: no cachear como 'failed'
        # para poder reintentar tras arreglar la key/cuota.
        if status in ("OVER_QUERY_LIMIT", "REQUEST_DENIED", "INVALID_REQUEST"):
            logger.error("Geocoding bloqueado (%s) para %r: %s", status, query, data.get("error_message"))
            return GeocodeResult(lat=None, lng=None, status="error_no_cache")

        results = data.get("results") or []
        if status != "OK" or not results:
            logger.info("Geocoding sin resultados (%s) para %r", status, query)
            return GeocodeResult(lat=None, lng=None, status="failed")

        first = results[0]
        geometry = first.get("geometry", {})
        location_type = geometry.get("location_type")

        # location_type APPROXIMATE = solo centro de ciudad/pueblo (sin calle).
        # Mostrar un pin "preciso" en el centro de un pueblo es engañoso para el
        # usuario; mejor caer al mapa de provincia (zoom out) en el publisher.
        # Aceptamos: ROOFTOP, RANGE_INTERPOLATED, GEOMETRIC_CENTER.
        if location_type == "APPROXIMATE":
            formatted = first.get("formatted_address")
            logger.info(
                "Geocoding APPROXIMATE (solo localidad) para %r → tratado como failed "
                "(formatted=%r)", query, formatted
            )
            return GeocodeResult(lat=None, lng=None, status="failed", formatted_address=formatted)

        loc = geometry["location"]
        formatted = first.get("formatted_address")
        return GeocodeResult(
            lat=float(loc["lat"]),
            lng=float(loc["lng"]),
            status="ok",
            formatted_address=formatted,
        )

    def geocode(
        self,
        direccion: Optional[str],
        localidad: Optional[str],
        provincia: Optional[str] = None,
        codigo_postal: Optional[str] = None,
    ) -> GeocodeResult:
        """
        Geocodifica una dirección. Devuelve siempre un GeocodeResult (ok/failed).

        Flujo:
        1. Cache hit (ok|failed)  → devuelve del cache.
        2. Cache miss             → llama a Google y cachea el resultado.
        3. Error transitorio      → NO cachea (status='error_no_cache'); reintentará la próxima vez.
        """
        direccion = direccion or ""
        localidad = localidad or ""
        provincia = provincia or ""
        codigo_postal = codigo_postal or ""

        if not direccion and not localidad:
            return GeocodeResult(lat=None, lng=None, status="failed")

        direccion_hash = _hash_address(direccion, localidad, provincia, codigo_postal)
        cached = self._cache_get(direccion_hash)
        if cached is not None:
            return cached

        query = _build_query(direccion, localidad, provincia, codigo_postal)
        result = self._call_google(query)

        # Solo persistimos resultados deterministas (ok / failed); los errores de cuota/key
        # se mantienen volátiles para reintentar tras arreglar la causa.
        if result.status in ("ok", "failed"):
            self._cache_put(direccion_hash, query, result)

        return result
