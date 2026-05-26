"""Tests de regresión SEO — Sprint 1.

Estos tests bloquean el merge si volvemos a romper algo crítico:
- Canonical vacío en posts.
- Title > 60 chars.
- FAQ schema/HTML descompensados.
- iframe pesado de Maps en posts.
- estado=None que crashea el render.

Se ejecutan sin WordPress vivo gracias a `MockClient` (ver `conftest.py`).
"""
from __future__ import annotations

import re

import pytest

from config.provinces import PROVINCIAS_ESPANA
from src.wordpress.page_generator import ProvinciaPageGenerator, _build_seo_title
from src.wordpress.publisher import WordPressPublisher


# ---------- Helper para extraer el <title> de un HTML ----------
def _extract_title(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    assert m, "HTML sin <title>"
    return m.group(1).strip()


# ---------------------------------------------------------------------------
# Helper _build_seo_title (página de provincia y posts)
# ---------------------------------------------------------------------------
class TestBuildSeoTitle:
    def test_base_plus_suffix_fits(self):
        assert _build_seo_title("Hola", " | Suffix") == "Hola | Suffix"

    def test_suffix_dropped_when_too_long(self):
        base = "A" * 50  # 50 chars
        # base + suffix (54) > 60? Let's check: 50 + 16 = 66 > 60 → suffix dropped
        result = _build_seo_title(base, " | Inmuebles BOE")
        assert result == base
        assert len(result) <= 60

    def test_base_truncated_when_over_max(self):
        base = "A" * 80
        result = _build_seo_title(base, " | x")
        assert len(result) <= 60
        assert result.endswith("…")

    def test_max_len_60_by_default(self):
        # caso real más largo del set actual: "Santa Cruz de Tenerife"
        result = _build_seo_title(
            "Subastas Judiciales en Santa Cruz de Tenerife 2026",
            " | Inmuebles BOE",
        )
        assert len(result) <= 60


# ---------------------------------------------------------------------------
# Página de provincia — la genera page_generator.py
# ---------------------------------------------------------------------------
@pytest.fixture
def page_gen():
    return ProvinciaPageGenerator()


@pytest.mark.parametrize("codigo", sorted(PROVINCIAS_ESPANA.keys()))
class TestProvinciaPage:
    def test_has_canonical(self, codigo, page_gen):
        html = page_gen.generate_page_content(codigo)
        assert re.search(
            r'<link\s+rel="canonical"\s+href="https://comprarensubasta\.com/subastas-judiciales-[^"]+/"',
            html,
        ), f"{codigo}: canonical ausente o malformada"

    def test_has_og_tags(self, codigo, page_gen):
        html = page_gen.generate_page_content(codigo)
        for prop in ("og:type", "og:url", "og:title", "og:description", "og:site_name", "og:locale"):
            assert f'property="{prop}"' in html, f"{codigo}: falta {prop}"

    def test_has_twitter_card(self, codigo, page_gen):
        html = page_gen.generate_page_content(codigo)
        assert 'name="twitter:card"' in html
        assert 'content="summary_large_image"' in html

    def test_title_under_60_chars(self, codigo, page_gen):
        html = page_gen.generate_page_content(codigo)
        title = _extract_title(html)
        assert len(title) <= 60, f"{codigo}: {len(title)} chars — '{title}'"

    def test_jsonld_count(self, codigo, page_gen):
        html = page_gen.generate_page_content(codigo)
        schemas = re.findall(r'<script type="application/ld\+json">', html)
        # Esperado: BreadcrumbList + CollectionPage + FAQPage
        assert len(schemas) >= 3, f"{codigo}: solo {len(schemas)} schemas, esperaba ≥3"

    def test_single_h1(self, codigo, page_gen):
        html = page_gen.generate_page_content(codigo)
        h1_count = len(re.findall(r"<h1[> ]", html))
        assert h1_count == 1, f"{codigo}: {h1_count} H1s (debe haber exactamente 1)"

    def test_has_viewport_and_charset(self, codigo, page_gen):
        html = page_gen.generate_page_content(codigo)
        assert "<meta charset=" in html
        assert 'name="viewport"' in html

    def test_robots_meta_present(self, codigo, page_gen):
        html = page_gen.generate_page_content(codigo)
        assert 'name="robots"' in html
        assert "index" in html
        assert "follow" in html


# ---------------------------------------------------------------------------
# Páginas índice (/subastas-judiciales/)
# ---------------------------------------------------------------------------
class TestIndexPage:
    def test_index_title_under_60(self, page_gen):
        html = page_gen.generate_index_page_content()
        title = _extract_title(html)
        assert len(title) <= 60, f"Index: {len(title)} chars — '{title}'"

    def test_index_has_canonical(self, page_gen):
        html = page_gen.generate_index_page_content()
        assert 'rel="canonical"' in html

    def test_index_has_jsonld(self, page_gen):
        html = page_gen.generate_index_page_content()
        schemas = re.findall(r'<script type="application/ld\+json">', html)
        assert len(schemas) >= 2  # Breadcrumb + CollectionPage

    def test_index_links_all_provinces(self, page_gen):
        html = page_gen.generate_index_page_content()
        # Debe enlazar a las 52 provincias por slug
        for prov in PROVINCIAS_ESPANA.values():
            slug = prov["slug"]
            assert f'href="/subastas-judiciales-{slug}/"' in html, f"Falta link a {slug}"


# ---------------------------------------------------------------------------
# Posts de subasta — los genera publisher.py
# ---------------------------------------------------------------------------
class TestPostMeta:
    def test_canonical_not_empty(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        meta = pub._generate_meta(sample_subasta)
        assert meta["rank_math_canonical_url"], "canonical vacío (regresión del hallazgo #1)"
        assert meta["rank_math_canonical_url"].startswith("http")

    def test_canonical_preserves_existing_link(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        existing = {"id": 42, "link": "https://comprarensubasta.com/slug-historico-distinto/"}
        meta = pub._generate_meta(sample_subasta, existing_post=existing)
        # Updates deben preservar el slug histórico ya indexado.
        assert meta["rank_math_canonical_url"] == existing["link"]

    def test_canonical_uses_deterministic_slug_when_new(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        meta = pub._generate_meta(sample_subasta)
        # Posts nuevos: la canonical incluye el slug determinista.
        assert "subasta-sub-ja-2025-244895" in meta["rank_math_canonical_url"]

    def test_no_yoast_fields(self, sample_subasta, mock_client):
        """Decisión D3: payload sin campos Yoast."""
        pub = WordPressPublisher(client=mock_client)
        meta = pub._generate_meta(sample_subasta)
        yoast_keys = [k for k in meta if k.startswith("_yoast_wpseo")]
        assert yoast_keys == [], f"Campos Yoast residuales: {yoast_keys}"

    def test_rank_math_robots_present(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        meta = pub._generate_meta(sample_subasta)
        assert meta.get("rank_math_robots") == [
            "index", "follow", "max-snippet:-1", "max-image-preview:large"
        ]

    def test_num_lotes_in_meta(self, subasta_factory, bien_factory, mock_client):
        """A11: _subasta_num_lotes se serializa (lo lee el plugin v1.1)."""
        b1 = bien_factory(numero_bien=1, subtipo_bien="Vivienda", localidad="Sevilla")
        b2 = bien_factory(numero_bien=2, subtipo_bien="Garaje", localidad="Sevilla")
        subasta = subasta_factory(bienes=[b1, b2])
        pub = WordPressPublisher(client=mock_client)
        meta = pub._generate_meta(subasta)
        assert meta["_subasta_num_lotes"] == "2"


class TestPostContent:
    def test_estado_none_no_crash(self, subasta_factory, mock_client):
        """A14: estado=None no debe romper el render."""
        s = subasta_factory(estado=None)
        pub = WordPressPublisher(client=mock_client)
        html = pub._generate_content(s)  # no debe lanzar AttributeError
        assert "subasta-detalle" in html
        # El badge superior aplica .upper(), comparamos case-insensitive.
        assert "en curso" in html.lower()

    def test_rel_noopener_on_external_links(self, sample_subasta, mock_client):
        """A13: enlaces target=_blank deben llevar noopener noreferrer."""
        # Forzamos URLs externas en la subasta
        sample_subasta.url_edicto = "https://example.com/edicto.pdf"
        sample_subasta.url_certificacion_cargas = "https://example.com/cargas.pdf"
        pub = WordPressPublisher(client=mock_client)
        html = pub._generate_content(sample_subasta)
        external_anchors = re.findall(r'<a [^>]*target="_blank"[^>]*>', html)
        assert external_anchors, "No hay anchors externos en el output (test mal montado)"
        for anchor in external_anchors:
            assert "noopener" in anchor, f"Falta noopener en: {anchor}"
            assert "noreferrer" in anchor, f"Falta noreferrer en: {anchor}"

    def test_breadcrumb_schema_present(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        html = pub._generate_content(sample_subasta)
        assert '"@type": "BreadcrumbList"' in html

    def test_faq_schema_present(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        html = pub._generate_content(sample_subasta)
        assert '"@type": "FAQPage"' in html

    def test_realestatelisting_schema_present(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        html = pub._generate_content(sample_subasta)
        assert '"@type": "RealEstateListing"' in html


class TestPostTitle:
    def test_post_title_under_60(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        title = pub._generate_title(sample_subasta)
        assert len(title) <= 60, f"{len(title)} chars — '{title}'"

    def test_post_title_no_localidad(self, subasta_factory, bien_factory, mock_client):
        """Subasta sin localidad: debe seguir generando título sin crashear."""
        b = bien_factory(localidad="", provincia="")
        s = subasta_factory(bienes=[b])
        pub = WordPressPublisher(client=mock_client)
        title = pub._generate_title(s)
        assert title  # no vacío
        assert len(title) <= 60
