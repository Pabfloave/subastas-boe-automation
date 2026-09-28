"""Tests de la revisión de septiembre de 2026: exactitud jurídica (LO 1/2025),
coherencia de la oferta en los CTA, autoría (E-E-A-T/GEO), categorías de
provincia y compatibilidad del plugin con los campos de Rank Math.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from config import settings
from config.provinces import PROVINCIAS_ESPANA
from src.wordpress import legal_texts
from src.wordpress.page_generator import ProvinciaPageGenerator
from src.wordpress.publisher import WordPressPublisher

PLUGIN = Path(__file__).parent.parent / "wordpress" / "subastas-meta-api.php"


def _jsonld_blocks(html: str) -> list:
    return [json.loads(m) for m in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


# ---------------------------------------------------------------------------
# Tipo de subasta y régimen jurídico
# ---------------------------------------------------------------------------
class TestLegalTexts:
    @pytest.mark.parametrize("ident,tipo,esperado", [
        ("SUB-JA-2026-1", "JUDICIAL EN VÍA DE APREMIO", "judicial"),
        ("SUB-JC-2026-1", "", "judicial"),
        ("SUB-AT-2026-1", "AGENCIA TRIBUTARIA", "de la Agencia Tributaria"),
        ("SUB-RC-2026-1", "RECAUDACIÓN TRIBUTARIA", "de recaudación tributaria"),
        ("SUB-NH-2026-1", "NOTARIAL HIPOTECARIA", "notarial"),
        ("SUB-GA-2026-1", "ADMINISTRATIVA GENERAL", "administrativa"),
    ])
    def test_etiqueta_tipo(self, ident, tipo, esperado):
        assert legal_texts.etiqueta_tipo(ident, tipo) == esperado

    def test_deposito_describe_ambos_regimenes(self):
        texto = legal_texts.DEPOSITO_JUDICIAL
        assert "20 %" in texto and "1.000 €" in texto and "5 %" in texto
        assert "669" in texto and "LO 1/2025" in texto

    def test_plazo_pago_ambos_regimenes(self):
        texto = legal_texts.PLAZO_PAGO_JUDICIAL
        assert "20 días" in texto and "40 días" in texto and "670" in texto


class TestPostLegalContent:
    def test_faq_judicial_usa_regimen_lo_1_2025(self, sample_subasta, mock_client):
        items = dict(WordPressPublisher(client=mock_client)._faq_items(sample_subasta))
        deposito = items["¿Cuánto depósito necesito para participar en esta subasta?"]
        assert "24.000" in deposito  # importe real del anuncio
        assert legal_texts.DEPOSITO_JUDICIAL in deposito
        pasos = items["¿Qué pasa si gano la subasta? ¿Cuáles son los siguientes pasos?"]
        assert "20 días" in pasos and "40 días" in pasos
        assert "20 días hábiles" not in pasos

    def test_subasta_aeat_no_se_presenta_como_judicial(self, subasta_factory, mock_client):
        s = subasta_factory(id_subasta="SUB-AT-2026-26R2886001207", tipo_subasta="AGENCIA TRIBUTARIA",
                            autoridad_gestora="Dependencia de Recaudación de Madrid")
        pub = WordPressPublisher(client=mock_client)
        html = pub._generate_content(s)
        assert "Detalles de la Subasta de la Agencia Tributaria en" in html
        assert "Juzgado Responsable" not in html
        assert "art. 669" not in html  # el régimen LEC no aplica a la AEAT
        desc = pub._generate_meta_description(s)
        assert desc.startswith("Subasta de la Agencia Tributaria de")

    def test_sin_errata_un_vivienda(self, sample_subasta, mock_client):
        html = WordPressPublisher(client=mock_client)._generate_content(sample_subasta)
        assert "un Vivienda" not in html and "un vivienda" not in html


# ---------------------------------------------------------------------------
# Oferta coherente con la respuesta automática + CTA
# ---------------------------------------------------------------------------
class TestPostCta:
    def test_no_promete_gratuidad(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        html = pub._generate_content(sample_subasta).lower()
        assert "gratuit" not in html
        assert "gratuit" not in pub._generate_meta_description(sample_subasta).lower()

    def test_muestra_condiciones_del_informe(self, sample_subasta, mock_client, monkeypatch):
        monkeypatch.setattr(settings, "INFORME_PRECIO", "72,60 € (IVA incluido)")
        html = WordPressPublisher(client=mock_client)._generate_content(sample_subasta)
        assert "72,60 € (IVA incluido)" in html

    def test_sin_precio_configurado_no_muestra_importe(self, sample_subasta, mock_client, monkeypatch):
        monkeypatch.setattr(settings, "INFORME_PRECIO", "")
        html = WordPressPublisher(client=mock_client)._generate_content(sample_subasta)
        assert "IVA incluido" not in html

    def test_cta_intermedio_y_final_mismo_enlace(self, sample_subasta, mock_client):
        html = WordPressPublisher(client=mock_client)._generate_content(sample_subasta)
        assert 'class="cta-intermedio"' in html
        hrefs = set(re.findall(r'<a href="([^"]+)" class="btn-cta"', html))
        assert len(hrefs) == 1
        href = hrefs.pop()
        assert "subasta=SUB-JA-2025-244895" in href
        # El query debe ir antes del fragment para llegar al servidor.
        assert href.index("?") < href.index("#")

    def test_resumen_factual(self, sample_subasta, mock_client):
        html = WordPressPublisher(client=mock_client)._generate_content(sample_subasta)
        m = re.search(r'<p class="resumen-subasta">(.*?)</p>', html, re.S)
        assert m and "SUB-JA-2025-244895" in m.group(1) and "120.000,00 €" in m.group(1)

    def test_resumen_multilote_sin_valor_global(self, subasta_factory, bien_factory, mock_client):
        from decimal import Decimal
        b1 = bien_factory(numero_bien=1, valor_subasta_lote=Decimal("50000"))
        b2 = bien_factory(numero_bien=2, valor_subasta_lote=Decimal("25000"))
        s = subasta_factory(bienes=[b1, b2], valor_subasta=Decimal("0"))
        html = WordPressPublisher(client=mock_client)._generate_content(s)
        m = re.search(r'<p class="resumen-subasta">(.*?)</p>', html, re.S)
        assert "alor de subasta: 0,00 €" not in m.group(1)
        assert "Valor de subasta de los 2 lotes: 75.000,00 €" in m.group(1)


# ---------------------------------------------------------------------------
# Autoría (E-E-A-T / GEO)
# ---------------------------------------------------------------------------
class TestAutoria:
    def test_post_muestra_responsable_y_schema(self, sample_subasta, mock_client, monkeypatch):
        monkeypatch.setattr(settings, "AUTOR_NOMBRE", "Nombre Apellido")
        monkeypatch.setattr(settings, "AUTOR_COLEGIADO", "123")
        monkeypatch.setattr(settings, "AUTOR_COLEGIO", "Colegio X")
        html = WordPressPublisher(client=mock_client)._generate_content(sample_subasta)
        assert "Abogado responsable: Nombre Apellido (colegiado n.º 123 del Colegio X)" in html
        legal = [b for b in _jsonld_blocks(html) if b.get("@type") == "LegalService"][0]
        assert legal["employee"]["name"] == "Nombre Apellido"
        assert legal["employee"]["hasCredential"]["identifier"] == "123"

    def test_sin_autor_configurado_no_hay_bloque(self, sample_subasta, mock_client, monkeypatch):
        monkeypatch.setattr(settings, "AUTOR_NOMBRE", "")
        html = WordPressPublisher(client=mock_client)._generate_content(sample_subasta)
        assert 'class="autor-box"' not in html
        legal = [b for b in _jsonld_blocks(html) if b.get("@type") == "LegalService"][0]
        assert "employee" not in legal


# ---------------------------------------------------------------------------
# Meta de Rank Math
# ---------------------------------------------------------------------------
class TestRankMathMeta:
    def test_seo_title_es_el_titulo_con_precio(self, sample_subasta, mock_client):
        pub = WordPressPublisher(client=mock_client)
        meta = pub._generate_meta(sample_subasta)
        assert meta["rank_math_title"] == pub._generate_title(sample_subasta)
        assert "120.000€" in meta["rank_math_title"]

    def test_plugin_registra_todas_las_claves_rank_math(self, sample_subasta, mock_client):
        """WordPress descarta en silencio las claves meta no registradas: toda
        clave rank_math_* que envía Python debe estar registrada en el plugin."""
        pub = WordPressPublisher(client=mock_client)
        meta = pub._generate_meta(sample_subasta, og_image_url="https://x/og.jpg")
        php = PLUGIN.read_text(encoding="utf-8")
        for key in (k for k in meta if k.startswith("rank_math_")):
            assert f"'{key}'" in php, f"{key} no está registrada en el plugin"

    @pytest.mark.skipif(shutil.which("php") is None, reason="php no disponible")
    def test_plugin_php_sin_errores_de_sintaxis(self):
        r = subprocess.run(["php", "-l", str(PLUGIN)], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# Categorías de provincia
# ---------------------------------------------------------------------------
class TestCategorias:
    def _calls(self, mock_client, monkeypatch):
        calls = []

        def fake(name, slug=None, parent=None):
            calls.append((name, slug))
            return len(calls)
        monkeypatch.setattr(mock_client, "get_or_create_category", fake)
        return calls

    def test_usa_nombre_y_slug_canonicos(self, subasta_factory, bien_factory, mock_client, monkeypatch):
        calls = self._calls(mock_client, monkeypatch)
        b = bien_factory(provincia="Valencia/València", provincia_codigo="46")
        WordPressPublisher(client=mock_client)._get_categories(subasta_factory(bien=b))
        assert ("Valencia", "valencia") in calls
        assert all(name != "Valencia/València" for name, _ in calls)

    def test_sin_codigo_no_crea_desconocida(self, subasta_factory, bien_factory, mock_client, monkeypatch):
        calls = self._calls(mock_client, monkeypatch)
        b = bien_factory(provincia="Araba/Álava", provincia_codigo="")
        WordPressPublisher(client=mock_client)._get_categories(subasta_factory(bien=b))
        assert all(slug != "desconocida" for _, slug in calls)

    def test_provincia_vacia_con_codigo_usa_nombre_canonico(self, subasta_factory, bien_factory, mock_client):
        b = bien_factory(provincia="", provincia_codigo="50", localidad="Épila")
        title = WordPressPublisher(client=mock_client)._generate_title(subasta_factory(bien=b))
        assert "(Zaragoza)" in title

    def test_client_busca_primero_por_slug(self, monkeypatch):
        from src.wordpress import client as client_mod

        class Resp:
            def __init__(self, data, status=200):
                self._data, self.status_code = data, status

            def json(self):
                return self._data

        pedidas = []

        def fake_get(url, headers=None, params=None, timeout=None):
            pedidas.append(params)
            if params.get("slug") == "valencia":
                return Resp([{"id": 77, "name": "Valencia"}])
            return Resp([])

        def fake_post(*a, **k):  # no debe crear nada
            raise AssertionError("no debería crear categoría")

        monkeypatch.setattr(client_mod.requests, "get", fake_get)
        monkeypatch.setattr(client_mod.requests, "post", fake_post)
        c = client_mod.WordPressClient.__new__(client_mod.WordPressClient)
        c.api_url, c.headers, c._categories_cache = "https://x/wp-json/wp/v2", {}, {}
        assert c.get_or_create_category("Valencia/València", "valencia", parent=5) == 77
        assert pedidas[0] == {"slug": "valencia"}


# ---------------------------------------------------------------------------
# Páginas de provincia e índice
# ---------------------------------------------------------------------------
@pytest.fixture
def page_gen():
    return ProvinciaPageGenerator()


class TestPaginasProvincia:
    @pytest.mark.parametrize("codigo", sorted(PROVINCIAS_ESPANA.keys()))
    def test_meta_description_max_160(self, codigo, page_gen):
        html = page_gen.generate_page_content(codigo)
        desc = re.search(r'<meta name="description" content="([^"]+)"', html).group(1)
        assert len(desc) <= 160, f"{codigo}: {len(desc)}"
        assert "gratuit" not in desc.lower()

    def test_sin_texto_juridico_desactualizado(self, page_gen):
        html = page_gen.generate_page_content("41")
        assert "20% del valor de tasaci" not in html
        assert "LO 1/2025" in html
        assert "Nuevo Régimen" not in html

    def test_cta_va_al_formulario_con_provincia(self, page_gen):
        html = page_gen.generate_page_content("41")
        assert 'href="/contacto/"' not in html
        m = re.search(r'<a href="([^"]+)" class="cta-btn"', html)
        assert m and "provincia=Sevilla" in m.group(1)
        assert m.group(1).startswith(settings.WP_CONTACT_FORM_URL.split("#")[0])

    def test_recuento_ssr_y_dato_fechado(self, page_gen, monkeypatch):
        monkeypatch.setattr(ProvinciaPageGenerator, "_fetch_posts_ssr",
                            lambda self, slug, limit=20: ([], 137))
        html = page_gen.generate_page_content("41")
        assert 'id="stats-total">137<' in html
        assert "recoge 137 subastas de inmuebles en Sevilla" in html

    def test_js_sustituye_cards_ssr_obsoletas(self, page_gen):
        html = page_gen.generate_page_content("41")
        assert "container.innerHTML = firstBatch.map(renderCard)" in html
        assert "firstBatch.slice(ssrCount)" not in html

    def test_indice_sin_contacto_ni_20_tasacion(self, page_gen):
        html = page_gen.generate_index_page_content()
        assert 'href="/contacto/"' not in html
        assert "20% del valor de tasación" not in html
