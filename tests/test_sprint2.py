"""Tests de regresión Sprint 2 (Acciones 3, 4, 8).

Cubren:
- A3: OG image en JSON-LD y meta + featured_media en el post.
- A4: iframe Google Maps sustituido por link card.
- A8: FAQ schema y HTML cuentan el mismo número de Q&A (fuente única).
- og_image.py: render local con Pillow + upload via MockClient.
"""
from __future__ import annotations

import json
import re

import pytest

from src.wordpress.publisher import WordPressPublisher


# ---------------------------------------------------------------------------
# A8 — FAQ unificada (fuente única)
# ---------------------------------------------------------------------------
class TestFaqUnified:
    def test_faq_items_count(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        items = pub._faq_items(sample_subasta)
        assert len(items) == 6

    def test_faq_html_count_matches_schema(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        schema_json = pub._generate_faq_schema(sample_subasta)
        html = pub._generate_faq_html(sample_subasta)

        # Contar Q&A en JSON-LD (parsear el bloque y contar Questions)
        match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            schema_json,
            re.S,
        )
        assert match
        payload = json.loads(match.group(1))
        schema_count = len(payload["mainEntity"])

        # Contar <details> en HTML
        html_count = html.count("<summary>")

        assert schema_count == html_count, (
            f"FAQ mismatch: schema={schema_count} preguntas, HTML={html_count}. "
            "Regresión del hallazgo #9 — ambos deben venir de _faq_items()."
        )

    def test_faq_html_uses_details_summary(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        html = pub._generate_faq_html(sample_subasta)
        # <details>/<summary> > <div class="faq-item"><h3>
        assert "<details class=\"faq-item\">" in html
        assert "<summary>" in html
        # No quedan los <h3> antiguos como cabecera de FAQ
        assert "<h3>¿" not in html  # un H3 con interrogación apertura es la cabecera vieja

    def test_faq_texts_personalized(self, subasta_factory, bien_factory, mock_client):
        b = bien_factory(subtipo_bien="Garaje", localidad="Burguillos")
        s = subasta_factory(bien=b, valor_subasta=12345)
        pub = WordPressPublisher(client=mock_client)
        items = pub._faq_items(s)
        # La primera pregunta lleva tipo + localidad
        q1, a1 = items[0]
        assert "Garaje" in q1.lower() or "garaje" in q1.lower()
        assert "Burguillos" in q1
        # La respuesta lleva el precio formateado
        assert "12.345" in a1 or "12345" in a1


# ---------------------------------------------------------------------------
# A4 — iframe Maps reemplazado por link card
# ---------------------------------------------------------------------------
class TestMapaLinkCard:
    def test_no_iframe_in_content(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        html = pub._generate_content(sample_subasta)
        assert "<iframe" not in html, (
            "iframe pesado (~1 MB) no debe estar — Sprint 2 A4 lo reemplazó por link card"
        )
        assert "google.com/maps?q=" not in html or "output=embed" not in html, (
            "El embed URL (que carga JS de Maps) no debe estar"
        )

    def test_mapa_link_present_when_address(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        html = pub._generate_content(sample_subasta)
        # El link card siempre debe llevar al search URL (no al embed)
        assert "google.com/maps/search/?api=1&query=" in html
        assert "mapa-link-card" in html

    def test_mapa_skipped_when_no_address(self, subasta_factory, bien_factory, mock_client):
        b = bien_factory(direccion="", localidad="Sevilla")
        s = subasta_factory(bien=b)
        pub = WordPressPublisher(client=mock_client)
        html = pub._generate_content(s)
        # Sin dirección no debería pintarse el bloque mapa (la clase aparece
        # en el CSS inline siempre, pero el <a class="mapa-link-card"> no).
        assert '<a href="https://www.google.com/maps/search' not in html

    def test_link_has_aria_label(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        html = pub._generate_content(sample_subasta)
        assert 'aria-label="Abrir ubicación' in html


# ---------------------------------------------------------------------------
# A3 — OG image en schema, meta y featured_media
# ---------------------------------------------------------------------------
class TestOgImage:
    def test_schema_has_image_when_og_url(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        og_url = "http://localhost:8080/wp-content/uploads/og-abc123.jpg"
        schema = pub._generate_schema_markup(sample_subasta, og_image_url=og_url)
        # Extraer el JSON-LD del RealEstateListing
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            schema,
            re.S,
        )
        rel = next(json.loads(b) for b in blocks if "RealEstateListing" in b)
        assert rel.get("image") == [og_url]

    def test_schema_has_dateModified(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        schema = pub._generate_schema_markup(sample_subasta)
        # dateModified presente
        assert '"dateModified"' in schema

    def test_meta_has_og_image_fields_when_url(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        og_url = "http://localhost:8080/wp-content/uploads/og.jpg"
        meta = pub._generate_meta(sample_subasta, og_image_url=og_url)
        assert meta["rank_math_facebook_image"] == og_url
        assert meta["rank_math_twitter_image"] == og_url

    def test_meta_no_og_fields_when_no_url(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        meta = pub._generate_meta(sample_subasta)  # og_image_url=None
        assert "rank_math_facebook_image" not in meta
        assert "rank_math_twitter_image" not in meta

    def test_publish_includes_featured_media(self, sample_subasta, mock_client, monkeypatch):
        """Si hay og_image_id, publish_subasta debe propagarlo como featured_media."""
        pub = WordPressPublisher(client=mock_client)
        # Forzamos un og_image generado (sin tener Pillow ni servidor real).
        monkeypatch.setattr(
            pub, "_get_or_create_og_image",
            lambda subasta: ("http://localhost:8080/og.jpg", 555),
        )
        pub.publish_subasta(sample_subasta)
        assert mock_client.created_posts, "create_post no fue llamado"
        last = mock_client.created_posts[-1]
        assert last.get("featured_media") == 555

    def test_publish_works_without_pillow(self, sample_subasta, mock_client, monkeypatch):
        """Si og_image no se genera (Pillow ausente), publish_subasta no rompe."""
        pub = WordPressPublisher(client=mock_client)
        monkeypatch.setattr(
            pub, "_get_or_create_og_image",
            lambda subasta: (None, None),
        )
        pub.publish_subasta(sample_subasta)
        last = mock_client.created_posts[-1]
        assert "featured_media" not in last


# ---------------------------------------------------------------------------
# og_image.py — render local con Pillow
# ---------------------------------------------------------------------------
class TestOgImageRender:
    def test_render_returns_path(self, tmp_path, monkeypatch):
        """Render genera un JPEG válido en el cache dir."""
        import src.wordpress.og_image as og_mod
        monkeypatch.setattr(og_mod, "CACHE_DIR", tmp_path)
        p = og_mod.render_og_image(
            tipo="Vivienda",
            localidad="Madrid",
            precio_str="250.000€",
            provincia="Madrid",
        )
        assert p is not None
        assert p.exists()
        assert p.suffix == ".jpg"
        # Magic bytes JPEG: FF D8 FF
        with open(p, "rb") as fh:
            head = fh.read(3)
        assert head[0] == 0xFF and head[1] == 0xD8

    def test_render_cache_hit(self, tmp_path, monkeypatch):
        """Segunda llamada con mismos args reutiliza el archivo cacheado."""
        import src.wordpress.og_image as og_mod
        monkeypatch.setattr(og_mod, "CACHE_DIR", tmp_path)
        p1 = og_mod.render_og_image(tipo="Local", localidad="Sevilla",
                                    precio_str="50.000€", provincia="Sevilla")
        mtime1 = p1.stat().st_mtime
        p2 = og_mod.render_og_image(tipo="Local", localidad="Sevilla",
                                    precio_str="50.000€", provincia="Sevilla")
        assert p1 == p2
        # No se ha regenerado (mtime conservado)
        assert p2.stat().st_mtime == mtime1

    def test_render_different_inputs_different_hashes(self, tmp_path, monkeypatch):
        import src.wordpress.og_image as og_mod
        monkeypatch.setattr(og_mod, "CACHE_DIR", tmp_path)
        p1 = og_mod.render_og_image("Vivienda", "Madrid", "100€", "Madrid")
        p2 = og_mod.render_og_image("Vivienda", "Madrid", "200€", "Madrid")
        assert p1.stem != p2.stem  # cache keys distintas
