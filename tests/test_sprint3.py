"""Tests Sprint 3 — A9 fonts, A10 CSS minify, A6 IndexNow, A2 SSR cards."""
from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from src.wordpress._html_utils import (
    fonts_links,
    minify_css,
    minify_inline_styles,
)
from src.wordpress.page_generator import ProvinciaPageGenerator


# ---------------------------------------------------------------------------
# A9 — Fonts no bloqueantes
# ---------------------------------------------------------------------------
class TestFontsLinks:
    def test_has_preconnect(self):
        out = fonts_links("family=DM+Sans")
        assert 'rel="preconnect"' in out
        assert "fonts.googleapis.com" in out
        assert "fonts.gstatic.com" in out

    def test_has_preload(self):
        out = fonts_links("family=DM+Sans")
        assert 'rel="preload"' in out
        assert 'as="style"' in out

    def test_has_non_blocking_pattern(self):
        out = fonts_links("family=DM+Sans")
        # media=print + onload swap → no bloquea render
        assert 'media="print"' in out
        assert "onload=\"this.media='all'\"" in out

    def test_has_noscript_fallback(self):
        out = fonts_links("family=DM+Sans")
        assert "<noscript>" in out

    def test_display_swap_in_url(self):
        out = fonts_links("family=DM+Sans")
        assert "display=swap" in out


# ---------------------------------------------------------------------------
# A10 — CSS minify
# ---------------------------------------------------------------------------
class TestCssMinify:
    def test_strips_comments(self):
        css = ".foo { color: red; /* comentario */ }"
        assert "/*" not in minify_css(css)
        assert "comentario" not in minify_css(css)

    def test_strips_whitespace_around_tokens(self):
        css = ".foo { color : red ; padding : 0 ; }"
        out = minify_css(css)
        assert ":red" in out
        assert "padding:0" in out

    def test_drops_trailing_semicolon(self):
        css = ".foo { color: red; }"
        # ";}" debe colapsar a "}"
        assert minify_css(css).endswith("}")
        assert ";}" not in minify_css(css)

    def test_minify_reduces_size(self):
        css = """
        .subasta-card {
            background: var(--color-bg);
            border: 1px solid var(--color-border);
            padding: 30px;
            margin-bottom: 30px;
        }
        """
        out = minify_css(css)
        assert len(out) < len(css) * 0.7  # al menos 30% reducción

    def test_minify_inline_styles_finds_and_minifies(self):
        html = """<html><head><style>
            body { padding: 0;
            margin: 0; }
        </style></head><body>x</body></html>"""
        out = minify_inline_styles(html)
        assert "<style>body{padding:0;margin:0}</style>" in out

    def test_minify_inline_styles_preserves_html(self):
        html = "<html><body><p>hola</p></body></html>"
        # Sin <style>, devuelve igual
        assert minify_inline_styles(html) == html


# ---------------------------------------------------------------------------
# A2 — SSR cards en página de provincia
# ---------------------------------------------------------------------------
class TestSsrCards:
    def test_ssr_container_has_data_attrs(self, monkeypatch):
        """Cuando SSR no devuelve nada, data-ssr-count debe ser 0."""
        gen = ProvinciaPageGenerator()
        # ya está mockeado por autouse fixture; aquí sólo verificamos
        html = gen.generate_page_content("41")
        assert 'data-ssr-count="0"' in html
        assert 'data-ssr-total="0"' in html

    def test_ssr_container_uses_subastas_grid_class(self):
        gen = ProvinciaPageGenerator()
        html = gen.generate_page_content("41")
        # El container ya es .subastas-grid (no se crea sub-div en cliente)
        assert 'id="subastas-container" class="subastas-grid"' in html

    def test_noscript_message_present(self):
        gen = ProvinciaPageGenerator()
        html = gen.generate_page_content("28")
        assert "<noscript>" in html
        assert "Activa JavaScript" in html

    def test_ssr_with_posts_renders_cards(self, monkeypatch):
        """Si _fetch_posts_ssr devuelve posts, el HTML debe contener
        cards estáticas con su título y link.
        """
        fake_posts = [
            {
                "id": 101,
                "link": "https://comprarensubasta.com/subasta-test-1/",
                "title": {"rendered": "Subasta Test Vivienda"},
                "subasta_meta": {
                    "_subasta_id": "SUB-TEST-1",
                    "_subasta_valor": "100000",
                    "_subasta_deposito": "20000",
                    "_subasta_fecha_fin": "2026-12-31T18:00:00",
                    "_subasta_estado": "Celebrándose",
                    "_bien_tipo": "Vivienda",
                    "_bien_localidad": "Sevilla",
                    "_subasta_num_lotes": "1",
                },
            },
            {
                "id": 102,
                "link": "https://comprarensubasta.com/subasta-test-2/",
                "title": {"rendered": "Subasta Test Garaje"},
                "subasta_meta": {
                    "_subasta_id": "SUB-TEST-2",
                    "_subasta_valor": "8000",
                    "_subasta_deposito": "1600",
                    "_subasta_fecha_fin": "2026-12-15T12:00:00",
                    "_subasta_estado": "Próxima",
                    "_bien_tipo": "Plaza de Garaje",
                    "_bien_localidad": "Dos Hermanas",
                    "_subasta_num_lotes": "1",
                },
            },
        ]
        monkeypatch.setattr(
            ProvinciaPageGenerator,
            "_fetch_posts_ssr",
            lambda self, slug, limit=20: (fake_posts, 42),
        )
        gen = ProvinciaPageGenerator()
        html = gen.generate_page_content("41")
        # Ambas cards SSR aparecen
        assert "Subasta Test Vivienda" in html
        assert "Subasta Test Garaje" in html
        assert "subasta-test-1" in html
        assert "subasta-test-2" in html
        # data-ssr-* refleja el count
        assert 'data-ssr-count="2"' in html
        assert 'data-ssr-total="42"' in html

    def test_render_card_ssr_handles_multi_lotes(self):
        post = {
            "id": 1,
            "link": "/x",
            "title": {"rendered": "Multi"},
            "subasta_meta": {
                "_subasta_num_lotes": "3",
                "_subasta_estado": "Celebrándose",
                "_subasta_valor": "50000",
                "_subasta_deposito": "10000",
                "_subasta_fecha_fin": "",
                "_bien_tipo": "Vivienda",
                "_bien_localidad": "Madrid",
                "_subasta_id": "M-1",
            },
        }
        out = ProvinciaPageGenerator._render_card_ssr(post)
        assert "📦 3 Lotes" in out
        assert "multi-lotes" in out
        assert 'class="badge badge-success">En Curso<' in out


# ---------------------------------------------------------------------------
# A6 — IndexNow + sitemap check
# ---------------------------------------------------------------------------
class TestIndexNow:
    def test_notify_empty_list_returns_false(self, mock_client):
        from src.wordpress.indexnow import notify
        assert notify([], mock_client) is False

    def test_notify_filters_non_http_urls(self, mock_client, monkeypatch):
        """URLs sin esquema http(s) se ignoran sin llamar a la red."""
        from src.wordpress import indexnow as inow

        called = {"post": False}

        def fake_post(*a, **kw):
            called["post"] = True
            raise AssertionError("No debería hacer POST con urls vacías")

        monkeypatch.setattr(inow.requests, "post", fake_post)
        # Solo URLs sin esquema → la lista filtrada queda vacía → return False
        result = inow.notify(["javascript:void(0)", "//foo.com"], mock_client)
        assert result is False
        assert called["post"] is False

    def test_notify_posts_to_bing(self, mock_client, monkeypatch, tmp_path):
        """Una llamada con URLs válidas debe hacer POST a bing.com/indexnow."""
        from src.wordpress import indexnow as inow

        # Aislar el cache local de la key
        monkeypatch.setattr(inow, "CACHE_ROOT", tmp_path)
        monkeypatch.setattr(inow, "KEY_FILE", tmp_path / "indexnow.key")
        monkeypatch.setattr(inow, "KEY_LOCATION_FILE", tmp_path / "indexnow.key_location")

        # Necesitamos que upload_media devuelva una URL plausible.
        # MockClient.upload_media exige que el archivo exista; el módulo lo crea.

        captured = {}

        class FakeResp:
            status_code = 200
            text = "OK"

        def fake_post(url, data=None, headers=None, timeout=None):
            captured["url"] = url
            captured["payload"] = data
            return FakeResp()

        monkeypatch.setattr(inow.requests, "post", fake_post)

        ok = inow.notify(
            ["https://example.com/a", "https://example.com/b"],
            mock_client,
            host="example.com",
        )
        assert ok is True
        assert captured["url"] == "https://www.bing.com/indexnow"
        import json
        payload = json.loads(captured["payload"])
        assert payload["host"] == "example.com"
        assert "key" in payload and "keyLocation" in payload
        assert payload["urlList"] == ["https://example.com/a", "https://example.com/b"]

    def test_flush_indexnow_empty_returns_false(self, mock_client):
        from src.wordpress.publisher import WordPressPublisher
        pub = WordPressPublisher(client=mock_client)
        assert pub.flush_indexnow() is False

    def test_publish_collects_urls(self, sample_subasta, mock_client):
        from src.wordpress.publisher import WordPressPublisher
        pub = WordPressPublisher(client=mock_client)
        pub.publish_subasta(sample_subasta)
        # MockClient.create_post devuelve link http://localhost:8080/…
        assert len(pub._published_urls) == 1
        assert pub._published_urls[0].startswith("http://localhost:8080/")


class TestSitemapCheck:
    def test_returns_true_on_xml_200(self, monkeypatch):
        from src.wordpress import indexnow as inow

        class FakeResp:
            status_code = 200
            text = '<?xml version="1.0"?><sitemapindex></sitemapindex>'

        monkeypatch.setattr(inow.requests, "get", lambda *a, **kw: FakeResp())
        assert inow.check_sitemap("https://example.com") is True

    def test_returns_false_on_404(self, monkeypatch):
        from src.wordpress import indexnow as inow

        class FakeResp:
            status_code = 404
            text = "Not Found"

        monkeypatch.setattr(inow.requests, "get", lambda *a, **kw: FakeResp())
        assert inow.check_sitemap("https://example.com") is False

    def test_returns_false_on_non_xml(self, monkeypatch):
        from src.wordpress import indexnow as inow

        class FakeResp:
            status_code = 200
            text = "<html>Lol no soy XML</html>"

        monkeypatch.setattr(inow.requests, "get", lambda *a, **kw: FakeResp())
        assert inow.check_sitemap("https://example.com") is False
