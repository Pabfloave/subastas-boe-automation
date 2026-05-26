"""Fixtures compartidos para los tests SEO.

Los tests no necesitan un WordPress vivo: usan un `MockClient` que registra
las llamadas y devuelve respuestas plausibles. Esto permite ejecutar la suite
en CI sin Docker.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pytest

from src.models.subasta import Bien, Subasta


class MockClient:
    """Stub del WordPressClient que graba llamadas y devuelve datos plausibles.

    Solo implementa los métodos consumidos por publisher.py y page_generator.py.
    Si un test futuro necesita otro método, se añade aquí — no mockeamos lo
    que no se usa.
    """

    def __init__(self) -> None:
        self.created_posts: List[Dict[str, Any]] = []
        self.updated_posts: List[Dict[str, Any]] = []
        # Espejo de los slugs deterministas creados para que un mismo
        # id_subasta produzca el mismo slug en dos llamadas.
        self._slug_cache: Dict[str, str] = {}

    # --- API consumida por publisher.py ---
    @staticmethod
    def make_subasta_slug(id_subasta: str) -> str:
        # Misma fórmula que client.py:make_subasta_slug
        return f"subasta-{id_subasta.lower().replace('_', '-')}"

    def get_post_by_subasta_id(self, id_subasta: str) -> Optional[dict]:
        # Devuelve None: los tests por defecto simulan post nuevo.
        # Tests específicos pueden monkeypatchear este método.
        return None

    def get_or_create_category(self, name: str, slug: Optional[str] = None,
                               parent: Optional[int] = None) -> int:
        return 1

    def get_or_create_tag(self, name: str) -> int:
        return 1

    def create_post(self, **post_data: Any) -> dict:
        self.created_posts.append(post_data)
        return {"id": 999, "link": f"http://localhost:8080/{post_data.get('slug', 'mock')}/"}

    def update_post(self, post_id: int, data: dict) -> dict:
        self.updated_posts.append({"id": post_id, **data})
        return {"id": post_id}

    def unpublish_post(self, post_id: int) -> bool:
        return True

    def upload_media(self, local_path, mime_type: str = "image/jpeg",
                     title: Optional[str] = None, alt_text: Optional[str] = None) -> Optional[dict]:
        """Mock: simula upload exitoso devolviendo URL plausible."""
        from pathlib import Path
        p = Path(local_path)
        # Si el archivo no existe, simulamos fallo (igual que el cliente real).
        if not p.exists():
            return None
        return {
            "id": 1000 + len([p for p in [self]]),  # ID distinto por instancia
            "source_url": f"http://localhost:8080/wp-content/uploads/{p.name}",
        }


@pytest.fixture
def mock_client() -> MockClient:
    return MockClient()


def _build_bien(**overrides: Any) -> Bien:
    """Crea un Bien con valores razonables que se pueden sobrescribir."""
    defaults: Dict[str, Any] = {
        "id_subasta": "SUB-JA-2025-244895",
        "tipo_bien": "Inmueble",
        "subtipo_bien": "Vivienda",
        "direccion": "Calle Mayor 10",
        "codigo_postal": "41001",
        "localidad": "Sevilla",
        "provincia": "Sevilla",
        "provincia_codigo": "41",
        "valor_tasacion": Decimal("150000.00"),
    }
    defaults.update(overrides)
    return Bien(**defaults)


def _build_subasta(**overrides: Any) -> Subasta:
    """Crea una Subasta de prueba con 1 bien. Los overrides se aplican antes
    de adjuntar el bien, así que `bienes=[...]` también es válido.
    """
    bien = overrides.pop("bien", None) or _build_bien()
    bienes = overrides.pop("bienes", None) or [bien]
    defaults: Dict[str, Any] = {
        "id_subasta": "SUB-JA-2025-244895",
        "tipo_subasta": "JUDICIAL EN VIA DE APREMIO",
        "estado": "Celebrándose",
        "valor_subasta": Decimal("120000.00"),
        "tasacion": Decimal("150000.00"),
        "importe_deposito": Decimal("24000.00"),
        "fecha_inicio": datetime(2026, 1, 1, 9, 0),
        "fecha_conclusion": datetime(2026, 2, 1, 18, 0),
        "url_detalle": "https://subastas.boe.es/detalleSubasta.php?idSub=SUB-JA-2025-244895",
        "autoridad_gestora": "Juzgado de Primera Instancia 16",
        "localidad_juzgado": "Sevilla",
        "bienes": bienes,
    }
    defaults.update(overrides)
    return Subasta(**defaults)


@pytest.fixture
def sample_subasta() -> Subasta:
    """Subasta de prueba estándar (vivienda en Sevilla, 1 lote)."""
    return _build_subasta()


@pytest.fixture
def subasta_factory():
    """Factory para crear Subasta con overrides arbitrarios."""
    return _build_subasta


@pytest.fixture
def bien_factory():
    return _build_bien
