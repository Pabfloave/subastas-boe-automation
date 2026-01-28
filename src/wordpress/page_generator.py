"""
Generador de páginas de subastas por provincia para WordPress.
Crea páginas dinámicas que cargan subastas desde la API REST.
Soporta las 52 provincias de España.
"""
import requests
from typing import Dict, Optional
from config import settings
from config.provinces import PROVINCIAS_ESPANA

# Cache de IDs de categorías (se llena dinámicamente)
_CATEGORIA_CACHE = {}


class ProvinciaPageGenerator:
    """Genera páginas de provincia para WordPress."""

    def __init__(self):
        self.base_url = settings.WP_URL
        self.auth = (settings.WP_USER, settings.WP_APP_PASSWORD)

    def _get_or_create_category(self, nombre: str, slug: str) -> int:
        """Obtiene o crea una categoría de provincia."""
        global _CATEGORIA_CACHE

        if slug in _CATEGORIA_CACHE:
            return _CATEGORIA_CACHE[slug]

        # Buscar categoría existente
        response = requests.get(
            f"{self.base_url}/wp-json/wp/v2/categories",
            params={"slug": slug}
        )
        if response.status_code == 200:
            cats = response.json()
            if cats:
                _CATEGORIA_CACHE[slug] = cats[0]["id"]
                return cats[0]["id"]

        # Buscar categoría padre "Subastas"
        response = requests.get(
            f"{self.base_url}/wp-json/wp/v2/categories",
            params={"slug": "subastas"}
        )
        parent_id = 0
        if response.status_code == 200:
            cats = response.json()
            if cats:
                parent_id = cats[0]["id"]

        # Crear nueva categoría
        response = requests.post(
            f"{self.base_url}/wp-json/wp/v2/categories",
            auth=self.auth,
            json={
                "name": nombre,
                "slug": slug,
                "parent": parent_id
            }
        )
        if response.status_code in (200, 201):
            cat_id = response.json()["id"]
            _CATEGORIA_CACHE[slug] = cat_id
            return cat_id

        return 0

    def generate_page_content(self, provincia_codigo: str) -> str:
        """
        Genera el contenido HTML completo para una página de provincia.

        Args:
            provincia_codigo: Código de provincia (ej: "41" para Sevilla)

        Returns:
            HTML completo de la página
        """
        prov = PROVINCIAS_ESPANA.get(provincia_codigo)
        if not prov:
            raise ValueError(f"Código de provincia no válido: {provincia_codigo}")

        nombre = prov["nombre"]
        slug = prov["slug"]

        return f'''<!-- wp:html -->
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Subastas Judiciales en {nombre} 2026 - CAFAVE INVESTMENT</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=DM+Serif+Display&display=swap" rel="stylesheet">
  <style>
    :root {{
      --color-primary: #0f172a;
      --color-secondary: #1e293b;
      --color-accent: #d97706;
      --color-accent-light: #f59e0b;
      --color-success: #059669;
      --color-success-light: #dcfce7;
      --color-info: #0284c7;
      --color-info-light: #dbeafe;
      --color-warning: #92400e;
      --color-warning-light: #fef3c7;
      --color-text: #1e293b;
      --color-text-muted: #64748b;
      --color-text-light: #475569;
      --color-bg: #ffffff;
      --color-bg-light: #f8fafc;
      --color-bg-warm: #fffbeb;
      --color-border: #e5e7eb;
      --font-display: 'DM Serif Display', Georgia, serif;
      --font-body: 'DM Sans', system-ui, sans-serif;
      --shadow-sm: 0 2px 8px rgba(0,0,0,0.05);
      --shadow-md: 0 8px 24px rgba(0,0,0,0.12);
      --radius-sm: 6px;
      --radius-md: 12px;
      --radius-lg: 15px;
      --radius-full: 9999px;
    }}

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      font-family: var(--font-body);
      color: var(--color-text);
      background: var(--color-bg-light);
      line-height: 1.6;
    }}

    .provincia-page {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 40px 20px;
    }}

    /* ===== SELECTOR DE PROVINCIAS ===== */
    .provincia-selector {{
      background: var(--color-bg);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 20px 30px;
      margin-bottom: 30px;
      box-shadow: var(--shadow-sm);
    }}

    .provincia-selector-title {{
      font-family: var(--font-display);
      font-size: 1.1em;
      margin-bottom: 15px;
      color: var(--color-text);
    }}

    .provincia-buttons {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}

    .provincia-btn {{
      padding: 10px 20px;
      border: 2px solid var(--color-border);
      border-radius: var(--radius-full);
      background: var(--color-bg);
      color: var(--color-text);
      font-family: var(--font-body);
      font-size: 0.9em;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      text-decoration: none;
    }}

    .provincia-btn:hover {{
      border-color: var(--color-accent);
      background: var(--color-bg-warm);
    }}

    .provincia-btn.active {{
      background: var(--color-primary);
      border-color: var(--color-primary);
      color: white;
    }}

    /* ===== INTRO SECTION ===== */
    .intro-section {{
      background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%);
      color: white;
      padding: 60px 40px;
      border-radius: var(--radius-lg);
      margin-bottom: 40px;
      text-align: center;
      position: relative;
      overflow: hidden;
    }}

    .intro-section::before {{
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
      pointer-events: none;
    }}

    .intro-section h1 {{
      font-family: var(--font-display);
      font-size: 2.5em;
      margin-bottom: 20px;
      font-weight: 400;
      position: relative;
    }}

    .intro-section p {{
      font-size: 1.1em;
      line-height: 1.8;
      max-width: 900px;
      margin: 0 auto 30px;
      opacity: 0.95;
    }}

    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 20px;
      margin-top: 30px;
    }}

    .stat-box {{
      background: rgba(255, 255, 255, 0.1);
      padding: 25px 20px;
      border-radius: var(--radius-md);
      text-align: center;
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.1);
    }}

    .stat-number {{
      font-family: var(--font-display);
      font-size: 2.8em;
      font-weight: 400;
      color: var(--color-accent-light);
      display: block;
      margin-bottom: 8px;
    }}

    .stat-label {{
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      opacity: 0.9;
    }}

    /* ===== LOADING ===== */
    .loading {{
      text-align: center;
      padding: 60px 20px;
    }}

    .loading-spinner {{
      width: 50px;
      height: 50px;
      border: 4px solid var(--color-border);
      border-top-color: var(--color-accent);
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin: 0 auto 20px;
    }}

    @keyframes spin {{
      to {{ transform: rotate(360deg); }}
    }}

    /* ===== SUBASTA CARDS ===== */
    .subastas-grid {{
      display: grid;
      gap: 30px;
    }}

    .subasta-card {{
      background: var(--color-bg);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 30px;
      box-shadow: var(--shadow-sm);
      transition: all 0.3s ease;
    }}

    .subasta-card:hover {{
      box-shadow: var(--shadow-md);
      transform: translateY(-2px);
    }}

    .subasta-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 20px;
      flex-wrap: wrap;
      gap: 15px;
    }}

    .subasta-title {{
      font-family: var(--font-display);
      font-size: 1.3em;
      font-weight: 400;
      color: var(--color-text);
      margin: 0 0 8px 0;
    }}

    .subasta-title a {{
      color: inherit;
      text-decoration: none;
    }}

    .subasta-title a:hover {{
      color: var(--color-accent);
    }}

    .subasta-ref {{
      font-size: 0.85em;
      color: var(--color-text-muted);
      font-family: 'SF Mono', 'Consolas', monospace;
      background: var(--color-bg-light);
      padding: 5px 12px;
      border-radius: var(--radius-sm);
    }}

    .badge {{
      display: inline-block;
      padding: 8px 16px;
      border-radius: var(--radius-full);
      font-size: 0.8em;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}

    .badge-success {{
      background: var(--color-success-light);
      color: #166534;
    }}

    .badge-info {{
      background: var(--color-info-light);
      color: #1e40af;
    }}

    .badge-warning {{
      background: var(--color-warning-light);
      color: var(--color-warning);
    }}

    .badge-lotes {{
      background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
      color: white;
    }}

    .badges-container {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}

    .subasta-card.multi-lotes {{
      border: 2px solid #3b82f6;
      position: relative;
    }}

    .subasta-card.multi-lotes::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 4px;
      background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
      border-radius: var(--radius-md) var(--radius-md) 0 0;
    }}

    .subasta-info-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 15px;
      margin-bottom: 20px;
    }}

    .info-item {{
      padding: 15px;
      background: var(--color-bg-light);
      border-radius: var(--radius-sm);
    }}

    .info-label {{
      font-size: 0.8em;
      color: var(--color-text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 5px;
    }}

    .info-value {{
      font-size: 1em;
      font-weight: 500;
      color: var(--color-text);
    }}

    .precio-destacado {{
      color: var(--color-accent);
      font-weight: 600;
      font-size: 1.1em;
    }}

    .btn-ver-subasta {{
      display: inline-block;
      padding: 12px 25px;
      background: var(--color-primary);
      color: white;
      border-radius: var(--radius-sm);
      text-decoration: none;
      font-weight: 500;
      transition: background 0.2s;
      margin-top: 15px;
    }}

    .btn-ver-subasta:hover {{
      background: var(--color-secondary);
    }}

    /* ===== CTA SECTION ===== */
    .cta-section {{
      background: linear-gradient(135deg, var(--color-accent) 0%, #b45309 100%);
      color: white;
      padding: 50px 40px;
      border-radius: var(--radius-lg);
      margin-top: 50px;
      text-align: center;
    }}

    .cta-section h2 {{
      font-family: var(--font-display);
      font-size: 2em;
      margin-bottom: 20px;
    }}

    .cta-section p {{
      font-size: 1.1em;
      max-width: 700px;
      margin: 0 auto 30px;
      opacity: 0.95;
    }}

    .cta-btn {{
      display: inline-block;
      padding: 15px 35px;
      background: white;
      color: var(--color-accent);
      border-radius: var(--radius-sm);
      text-decoration: none;
      font-weight: 600;
      font-size: 1.1em;
      transition: transform 0.2s;
    }}

    .cta-btn:hover {{
      transform: scale(1.05);
    }}

    /* ===== RESPONSIVE ===== */
    @media (max-width: 768px) {{
      .intro-section {{ padding: 40px 25px; }}
      .intro-section h1 {{ font-size: 1.8em; }}
      .provincia-selector {{ padding: 15px 20px; }}
      .provincia-btn {{ padding: 8px 15px; font-size: 0.85em; }}
      .subasta-card {{ padding: 20px; }}
    }}
  </style>
</head>
<body>

<div class="provincia-page">

  <!-- ===== SELECTOR DE PROVINCIAS ===== -->
  <nav class="provincia-selector">
    <h3 class="provincia-selector-title">🗺️ Subastas por Provincia en España</h3>
    <details>
      <summary style="cursor:pointer;font-weight:500;margin-bottom:10px;">Ver todas las provincias (52)</summary>
      <div class="provincia-buttons">
        <a href="/subastas-judiciales-a-coruna/" class="provincia-btn{' active' if slug == 'a-coruna' else ''}">A Coruña</a>
        <a href="/subastas-judiciales-alava/" class="provincia-btn{' active' if slug == 'alava' else ''}">Álava</a>
        <a href="/subastas-judiciales-albacete/" class="provincia-btn{' active' if slug == 'albacete' else ''}">Albacete</a>
        <a href="/subastas-judiciales-alicante/" class="provincia-btn{' active' if slug == 'alicante' else ''}">Alicante</a>
        <a href="/subastas-judiciales-almeria/" class="provincia-btn{' active' if slug == 'almeria' else ''}">Almería</a>
        <a href="/subastas-judiciales-asturias/" class="provincia-btn{' active' if slug == 'asturias' else ''}">Asturias</a>
        <a href="/subastas-judiciales-avila/" class="provincia-btn{' active' if slug == 'avila' else ''}">Ávila</a>
        <a href="/subastas-judiciales-badajoz/" class="provincia-btn{' active' if slug == 'badajoz' else ''}">Badajoz</a>
        <a href="/subastas-judiciales-baleares/" class="provincia-btn{' active' if slug == 'baleares' else ''}">Baleares</a>
        <a href="/subastas-judiciales-barcelona/" class="provincia-btn{' active' if slug == 'barcelona' else ''}">Barcelona</a>
        <a href="/subastas-judiciales-burgos/" class="provincia-btn{' active' if slug == 'burgos' else ''}">Burgos</a>
        <a href="/subastas-judiciales-caceres/" class="provincia-btn{' active' if slug == 'caceres' else ''}">Cáceres</a>
        <a href="/subastas-judiciales-cadiz/" class="provincia-btn{' active' if slug == 'cadiz' else ''}">Cádiz</a>
        <a href="/subastas-judiciales-cantabria/" class="provincia-btn{' active' if slug == 'cantabria' else ''}">Cantabria</a>
        <a href="/subastas-judiciales-castellon/" class="provincia-btn{' active' if slug == 'castellon' else ''}">Castellón</a>
        <a href="/subastas-judiciales-ceuta/" class="provincia-btn{' active' if slug == 'ceuta' else ''}">Ceuta</a>
        <a href="/subastas-judiciales-ciudad-real/" class="provincia-btn{' active' if slug == 'ciudad-real' else ''}">Ciudad Real</a>
        <a href="/subastas-judiciales-cordoba/" class="provincia-btn{' active' if slug == 'cordoba' else ''}">Córdoba</a>
        <a href="/subastas-judiciales-cuenca/" class="provincia-btn{' active' if slug == 'cuenca' else ''}">Cuenca</a>
        <a href="/subastas-judiciales-girona/" class="provincia-btn{' active' if slug == 'girona' else ''}">Girona</a>
        <a href="/subastas-judiciales-granada/" class="provincia-btn{' active' if slug == 'granada' else ''}">Granada</a>
        <a href="/subastas-judiciales-guadalajara/" class="provincia-btn{' active' if slug == 'guadalajara' else ''}">Guadalajara</a>
        <a href="/subastas-judiciales-guipuzcoa/" class="provincia-btn{' active' if slug == 'guipuzcoa' else ''}">Guipúzcoa</a>
        <a href="/subastas-judiciales-huelva/" class="provincia-btn{' active' if slug == 'huelva' else ''}">Huelva</a>
        <a href="/subastas-judiciales-huesca/" class="provincia-btn{' active' if slug == 'huesca' else ''}">Huesca</a>
        <a href="/subastas-judiciales-jaen/" class="provincia-btn{' active' if slug == 'jaen' else ''}">Jaén</a>
        <a href="/subastas-judiciales-la-rioja/" class="provincia-btn{' active' if slug == 'la-rioja' else ''}">La Rioja</a>
        <a href="/subastas-judiciales-las-palmas/" class="provincia-btn{' active' if slug == 'las-palmas' else ''}">Las Palmas</a>
        <a href="/subastas-judiciales-leon/" class="provincia-btn{' active' if slug == 'leon' else ''}">León</a>
        <a href="/subastas-judiciales-lleida/" class="provincia-btn{' active' if slug == 'lleida' else ''}">Lleida</a>
        <a href="/subastas-judiciales-lugo/" class="provincia-btn{' active' if slug == 'lugo' else ''}">Lugo</a>
        <a href="/subastas-judiciales-madrid/" class="provincia-btn{' active' if slug == 'madrid' else ''}">Madrid</a>
        <a href="/subastas-judiciales-malaga/" class="provincia-btn{' active' if slug == 'malaga' else ''}">Málaga</a>
        <a href="/subastas-judiciales-melilla/" class="provincia-btn{' active' if slug == 'melilla' else ''}">Melilla</a>
        <a href="/subastas-judiciales-murcia/" class="provincia-btn{' active' if slug == 'murcia' else ''}">Murcia</a>
        <a href="/subastas-judiciales-navarra/" class="provincia-btn{' active' if slug == 'navarra' else ''}">Navarra</a>
        <a href="/subastas-judiciales-ourense/" class="provincia-btn{' active' if slug == 'ourense' else ''}">Ourense</a>
        <a href="/subastas-judiciales-palencia/" class="provincia-btn{' active' if slug == 'palencia' else ''}">Palencia</a>
        <a href="/subastas-judiciales-pontevedra/" class="provincia-btn{' active' if slug == 'pontevedra' else ''}">Pontevedra</a>
        <a href="/subastas-judiciales-salamanca/" class="provincia-btn{' active' if slug == 'salamanca' else ''}">Salamanca</a>
        <a href="/subastas-judiciales-santa-cruz-tenerife/" class="provincia-btn{' active' if slug == 'santa-cruz-tenerife' else ''}">S.C. Tenerife</a>
        <a href="/subastas-judiciales-segovia/" class="provincia-btn{' active' if slug == 'segovia' else ''}">Segovia</a>
        <a href="/subastas-judiciales-sevilla/" class="provincia-btn{' active' if slug == 'sevilla' else ''}">Sevilla</a>
        <a href="/subastas-judiciales-soria/" class="provincia-btn{' active' if slug == 'soria' else ''}">Soria</a>
        <a href="/subastas-judiciales-tarragona/" class="provincia-btn{' active' if slug == 'tarragona' else ''}">Tarragona</a>
        <a href="/subastas-judiciales-teruel/" class="provincia-btn{' active' if slug == 'teruel' else ''}">Teruel</a>
        <a href="/subastas-judiciales-toledo/" class="provincia-btn{' active' if slug == 'toledo' else ''}">Toledo</a>
        <a href="/subastas-judiciales-valencia/" class="provincia-btn{' active' if slug == 'valencia' else ''}">Valencia</a>
        <a href="/subastas-judiciales-valladolid/" class="provincia-btn{' active' if slug == 'valladolid' else ''}">Valladolid</a>
        <a href="/subastas-judiciales-vizcaya/" class="provincia-btn{' active' if slug == 'vizcaya' else ''}">Vizcaya</a>
        <a href="/subastas-judiciales-zamora/" class="provincia-btn{' active' if slug == 'zamora' else ''}">Zamora</a>
        <a href="/subastas-judiciales-zaragoza/" class="provincia-btn{' active' if slug == 'zaragoza' else ''}">Zaragoza</a>
      </div>
    </details>
  </nav>

  <!-- ===== INTRO SECTION ===== -->
  <section class="intro-section">
    <h1>🏛️ Subastas Judiciales en {nombre} 2026</h1>
    <p>Acceda a las mejores oportunidades de inversión inmobiliaria en {nombre} mediante subastas judiciales del BOE. Información actualizada, documentación completa y asesoramiento profesional de CAFAVE INVESTMENT.</p>

    <div class="stats-grid">
      <div class="stat-box">
        <span class="stat-number" id="stats-total">-</span>
        <span class="stat-label">Subastas Activas</span>
      </div>
      <div class="stat-box">
        <span class="stat-number">20%</span>
        <span class="stat-label">Depósito Nuevo Régimen</span>
      </div>
      <div class="stat-box">
        <span class="stat-number">24h</span>
        <span class="stat-label">Actualización Diaria</span>
      </div>
    </div>
  </section>

  <!-- ===== SUBASTAS CONTAINER ===== -->
  <div id="subastas-container">
    <div class="loading">
      <div class="loading-spinner"></div>
      <p>Cargando subastas de {nombre}...</p>
    </div>
  </div>

  <!-- ===== CTA SECTION ===== -->
  <section class="cta-section">
    <h2>¿Necesita Asesoramiento Profesional?</h2>
    <p>Nuestro equipo de expertos en subastas judiciales puede ayudarle a encontrar la mejor oportunidad de inversión en {nombre} y gestionar todo el proceso.</p>
    <a href="/contacto/" class="cta-btn">📞 Solicitar Consulta Gratuita</a>
  </section>

</div>

<script>
(function() {{
  const API_URL = '{self.base_url}/wp-json/wp/v2';
  const PROVINCIA_SLUG = '{slug}';
  const PROVINCIA = '{nombre}';

  // Función para formatear precios
  function formatPrice(value) {{
    if (!value || value === '0') return 'No disponible';
    const num = parseFloat(value);
    return num.toLocaleString('es-ES', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}) + ' €';
  }}

  // Función para formatear fechas
  function formatDate(dateStr) {{
    if (!dateStr) return 'No disponible';
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-ES', {{
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }});
  }}

  // Cargar subastas
  async function loadSubastas() {{
    try {{
      // Primero obtener el ID de la categoría por slug
      const catResponse = await fetch(`${{API_URL}}/categories?slug=${{PROVINCIA_SLUG}}`);
      const categories = await catResponse.json();

      if (!categories || categories.length === 0) {{
        // No hay categoría = no hay subastas para esta provincia
        document.getElementById('stats-total').textContent = '0';
        document.getElementById('subastas-container').innerHTML = `
          <div style="text-align: center; padding: 60px 20px;">
            <p style="font-size: 1.2em; color: var(--color-text-muted);">
              No hay subastas activas en ${{PROVINCIA}} en este momento.
            </p>
            <p style="margin-top: 15px;">Vuelva a consultar pronto o explore otras provincias.</p>
          </div>
        `;
        return;
      }}

      const categoriaId = categories[0].id;
      const response = await fetch(`${{API_URL}}/posts?categories=${{categoriaId}}&per_page=50&_embed`);
      const subastas = await response.json();

      // Actualizar estadísticas
      document.getElementById('stats-total').textContent = subastas.length;

      const container = document.getElementById('subastas-container');

      if (subastas.length === 0) {{
        container.innerHTML = `
          <div style="text-align: center; padding: 60px 20px;">
            <p style="font-size: 1.2em; color: var(--color-text-muted);">
              No hay subastas activas en ${{PROVINCIA}} en este momento.
            </p>
            <p style="margin-top: 15px;">Vuelva a consultar pronto o explore otras provincias.</p>
          </div>
        `;
        return;
      }}

      let html = '<div class="subastas-grid">';

      for (const subasta of subastas) {{
        // Intentar obtener meta del plugin personalizado o del meta estándar
        const meta = subasta.subasta_meta || subasta.meta || {{}};
        const titulo = subasta.title.rendered;
        const link = subasta.link;
        const id = meta._subasta_id || meta['_subasta_id'] || '';
        const valor = formatPrice(meta._subasta_valor || meta['_subasta_valor']);
        const deposito = formatPrice(meta._subasta_deposito || meta['_subasta_deposito']);
        const fechaFin = formatDate(meta._subasta_fecha_fin || meta['_subasta_fecha_fin']);
        const estado = meta._subasta_estado || meta['_subasta_estado'] || 'En curso';
        const tipo = meta._bien_tipo || meta['_bien_tipo'] || 'Inmueble';
        const localidad = meta._bien_localidad || meta['_bien_localidad'] || PROVINCIA;
        const numLotes = parseInt(meta._subasta_num_lotes || meta['_subasta_num_lotes'] || '1');

        // Determinar badge
        let badgeClass = 'badge-info';
        let badgeText = estado;
        if (estado.toLowerCase().includes('celebr')) {{
          badgeClass = 'badge-success';
          badgeText = 'En Curso';
        }}

        // Badge de múltiples lotes
        const lotesBadge = numLotes > 1 ? `<span class="badge badge-lotes">📦 ${{numLotes}} Lotes</span>` : '';

        html += `
          <article class="subasta-card ${{numLotes > 1 ? 'multi-lotes' : ''}}">
            <header class="subasta-header">
              <div>
                <h2 class="subasta-title"><a href="${{link}}">${{titulo}}</a></h2>
                <span class="subasta-ref">Ref: ${{id}}</span>
              </div>
              <div class="badges-container">
                ${{lotesBadge}}
                <span class="badge ${{badgeClass}}">${{badgeText}}</span>
              </div>
            </header>

            <div class="subasta-info-grid">
              <div class="info-item">
                <div class="info-label">💰 Valor Subasta</div>
                <div class="info-value precio-destacado">${{valor}}</div>
              </div>
              <div class="info-item">
                <div class="info-label">🏷️ Depósito</div>
                <div class="info-value">${{deposito}}</div>
              </div>
              <div class="info-item">
                <div class="info-label">📅 Finaliza</div>
                <div class="info-value">${{fechaFin}}</div>
              </div>
              <div class="info-item">
                <div class="info-label">🏠 Tipo</div>
                <div class="info-value">${{tipo}}</div>
              </div>
              <div class="info-item">
                <div class="info-label">📍 Localidad</div>
                <div class="info-value">${{localidad}}</div>
              </div>
            </div>

            <a href="${{link}}" class="btn-ver-subasta">Ver Detalles Completos →</a>
          </article>
        `;
      }}

      html += '</div>';
      container.innerHTML = html;

    }} catch (error) {{
      console.error('Error cargando subastas:', error);
      document.getElementById('subastas-container').innerHTML = `
        <div style="text-align: center; padding: 60px 20px; color: var(--color-warning);">
          <p>Error al cargar las subastas. Por favor, recargue la página.</p>
        </div>
      `;
    }}
  }}

  // Cargar al iniciar
  loadSubastas();
}})();
</script>

</body>
</html>
<!-- /wp:html -->'''

    def create_page(self, provincia_codigo: str, update_existing: bool = True) -> dict:
        """
        Crea o actualiza una página de provincia en WordPress.

        Args:
            provincia_codigo: Código de provincia
            update_existing: Si actualizar página existente

        Returns:
            Diccionario con información del resultado
        """
        prov = PROVINCIAS_ESPANA.get(provincia_codigo)
        if not prov:
            raise ValueError(f"Código de provincia no válido: {provincia_codigo}")
        slug = f"subastas-judiciales-{prov['slug']}"
        title = f"Subastas Judiciales en {prov['nombre']} 2026 | Inmuebles BOE Actualizado"
        content = self.generate_page_content(provincia_codigo)

        # Verificar si ya existe
        existing = self._get_existing_page(slug)

        if existing and update_existing:
            # Actualizar
            response = requests.post(
                f"{self.base_url}/wp-json/wp/v2/pages/{existing['id']}",
                auth=self.auth,
                json={
                    "title": title,
                    "content": content,
                    "status": "publish"
                }
            )
            result = response.json()
            return {
                "action": "updated",
                "id": result.get("id"),
                "slug": slug,
                "provincia": prov["nombre"]
            }
        elif not existing:
            # Crear nueva
            response = requests.post(
                f"{self.base_url}/wp-json/wp/v2/pages",
                auth=self.auth,
                json={
                    "title": title,
                    "content": content,
                    "slug": slug,
                    "status": "publish"
                }
            )
            result = response.json()
            return {
                "action": "created",
                "id": result.get("id"),
                "slug": slug,
                "provincia": prov["nombre"]
            }
        else:
            return {
                "action": "skipped",
                "id": existing["id"],
                "slug": slug,
                "provincia": prov["nombre"]
            }

    def _get_existing_page(self, slug: str) -> Optional[dict]:
        """Busca una página existente por slug."""
        response = requests.get(
            f"{self.base_url}/wp-json/wp/v2/pages",
            params={"slug": slug}
        )
        pages = response.json()
        return pages[0] if pages else None

    def generate_index_page_content(self) -> str:
        """
        Genera el contenido HTML para la página índice de subastas
        con enlaces a todas las provincias organizadas por comunidad autónoma.
        """
        # Agrupar provincias por comunidad autónoma
        comunidades = {}
        for codigo, data in PROVINCIAS_ESPANA.items():
            comunidad = data.get("comunidad", "Otras")
            if comunidad not in comunidades:
                comunidades[comunidad] = []
            comunidades[comunidad].append({
                "codigo": codigo,
                "nombre": data["nombre"],
                "slug": data["slug"]
            })

        # Ordenar comunidades y provincias
        comunidades_ordenadas = sorted(comunidades.keys())
        for comunidad in comunidades_ordenadas:
            comunidades[comunidad].sort(key=lambda x: x["nombre"])

        # Generar HTML de las provincias por comunidad
        provincias_html = ""
        for comunidad in comunidades_ordenadas:
            provincias_html += f'''
        <div class="comunidad-section">
          <h3 class="comunidad-title">{comunidad}</h3>
          <div class="provincias-grid">
'''
            for prov in comunidades[comunidad]:
                provincias_html += f'''            <a href="/subastas-judiciales-{prov['slug']}/" class="provincia-card">
              <span class="provincia-name">{prov['nombre']}</span>
              <span class="provincia-arrow">→</span>
            </a>
'''
            provincias_html += '''          </div>
        </div>
'''

        return f'''<!-- wp:html -->
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Subastas Judiciales en España 2026 - Todas las Provincias | CAFAVE INVESTMENT</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
  <style>
    :root {{
      --color-primary: #0f172a;
      --color-secondary: #1e293b;
      --color-accent: #d97706;
      --color-accent-light: #f59e0b;
      --color-text: #1e293b;
      --color-text-muted: #64748b;
      --color-bg: #ffffff;
      --color-bg-light: #f8fafc;
      --color-bg-warm: #fffbeb;
      --color-border: #e5e7eb;
      --font-display: 'DM Serif Display', Georgia, serif;
      --font-body: 'DM Sans', system-ui, sans-serif;
      --shadow-sm: 0 2px 8px rgba(0,0,0,0.05);
      --shadow-md: 0 8px 24px rgba(0,0,0,0.12);
      --radius-sm: 6px;
      --radius-md: 12px;
      --radius-lg: 15px;
    }}

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      font-family: var(--font-body);
      color: var(--color-text);
      background: var(--color-bg-light);
      line-height: 1.6;
    }}

    .subastas-index {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 40px 20px;
    }}

    /* Hero Section */
    .hero-section {{
      background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-secondary) 100%);
      color: white;
      padding: 60px 40px;
      border-radius: var(--radius-lg);
      margin-bottom: 50px;
      text-align: center;
      position: relative;
      overflow: hidden;
    }}

    .hero-section::before {{
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
      pointer-events: none;
    }}

    .hero-section h1 {{
      font-family: var(--font-display);
      font-size: 2.8em;
      margin-bottom: 20px;
      font-weight: 400;
      position: relative;
    }}

    .hero-section p {{
      font-size: 1.15em;
      line-height: 1.8;
      max-width: 800px;
      margin: 0 auto;
      opacity: 0.95;
    }}

    .stats-bar {{
      display: flex;
      justify-content: center;
      gap: 40px;
      margin-top: 35px;
      flex-wrap: wrap;
    }}

    .stat-item {{
      text-align: center;
    }}

    .stat-number {{
      font-family: var(--font-display);
      font-size: 2.5em;
      color: var(--color-accent-light);
      display: block;
    }}

    .stat-label {{
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 1px;
      opacity: 0.9;
    }}

    /* Comunidad Sections */
    .comunidad-section {{
      margin-bottom: 40px;
    }}

    .comunidad-title {{
      font-family: var(--font-display);
      font-size: 1.5em;
      color: var(--color-primary);
      margin-bottom: 20px;
      padding-bottom: 10px;
      border-bottom: 2px solid var(--color-accent);
      display: inline-block;
    }}

    .provincias-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 15px;
    }}

    .provincia-card {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 18px 20px;
      background: var(--color-bg);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-sm);
      text-decoration: none;
      color: var(--color-text);
      transition: all 0.2s ease;
      box-shadow: var(--shadow-sm);
    }}

    .provincia-card:hover {{
      border-color: var(--color-accent);
      background: var(--color-bg-warm);
      transform: translateY(-2px);
      box-shadow: var(--shadow-md);
    }}

    .provincia-name {{
      font-weight: 500;
    }}

    .provincia-arrow {{
      color: var(--color-accent);
      font-size: 1.2em;
      transition: transform 0.2s;
    }}

    .provincia-card:hover .provincia-arrow {{
      transform: translateX(5px);
    }}

    /* Info Section */
    .info-section {{
      background: var(--color-bg);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 40px;
      margin-top: 50px;
    }}

    .info-section h2 {{
      font-family: var(--font-display);
      font-size: 1.8em;
      margin-bottom: 20px;
      color: var(--color-primary);
    }}

    .info-section p {{
      color: var(--color-text-muted);
      margin-bottom: 15px;
    }}

    .info-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 25px;
      margin-top: 30px;
    }}

    .info-card {{
      padding: 25px;
      background: var(--color-bg-light);
      border-radius: var(--radius-sm);
    }}

    .info-card h3 {{
      font-size: 1.1em;
      margin-bottom: 10px;
      color: var(--color-primary);
    }}

    .info-card p {{
      font-size: 0.95em;
      margin: 0;
    }}

    /* CTA Section */
    .cta-section {{
      background: linear-gradient(135deg, var(--color-accent) 0%, #b45309 100%);
      color: white;
      padding: 50px 40px;
      border-radius: var(--radius-lg);
      margin-top: 50px;
      text-align: center;
    }}

    .cta-section h2 {{
      font-family: var(--font-display);
      font-size: 2em;
      margin-bottom: 15px;
    }}

    .cta-section p {{
      font-size: 1.1em;
      max-width: 600px;
      margin: 0 auto 25px;
      opacity: 0.95;
    }}

    .cta-btn {{
      display: inline-block;
      padding: 15px 35px;
      background: white;
      color: var(--color-accent);
      border-radius: var(--radius-sm);
      text-decoration: none;
      font-weight: 600;
      font-size: 1.1em;
      transition: transform 0.2s;
    }}

    .cta-btn:hover {{
      transform: scale(1.05);
    }}

    /* Responsive */
    @media (max-width: 768px) {{
      .hero-section {{ padding: 40px 25px; }}
      .hero-section h1 {{ font-size: 2em; }}
      .stats-bar {{ gap: 25px; }}
      .provincias-grid {{ grid-template-columns: 1fr; }}
      .info-section {{ padding: 25px; }}
    }}
  </style>
</head>
<body>

<div class="subastas-index">

  <!-- Hero Section -->
  <section class="hero-section">
    <h1>Subastas Judiciales en España 2026</h1>
    <p>Acceda a todas las subastas judiciales del BOE organizadas por provincia. Información actualizada diariamente con las mejores oportunidades de inversión inmobiliaria en toda España.</p>

    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-number">52</span>
        <span class="stat-label">Provincias</span>
      </div>
      <div class="stat-item">
        <span class="stat-number">24h</span>
        <span class="stat-label">Actualización</span>
      </div>
      <div class="stat-item">
        <span class="stat-number">100%</span>
        <span class="stat-label">Oficial BOE</span>
      </div>
    </div>
  </section>

  <!-- Provincias por Comunidad Autónoma -->
  <div class="provincias-container">
{provincias_html}
  </div>

  <!-- Info Section -->
  <section class="info-section">
    <h2>¿Cómo funcionan las subastas judiciales?</h2>
    <p>Las subastas judiciales son procedimientos legales donde se venden bienes embargados para saldar deudas. Representan una excelente oportunidad para adquirir inmuebles por debajo del precio de mercado.</p>

    <div class="info-grid">
      <div class="info-card">
        <h3>Depósito del 20%</h3>
        <p>Para participar necesita depositar el 20% del valor de tasación como garantía.</p>
      </div>
      <div class="info-card">
        <h3>Proceso 100% Online</h3>
        <p>Las subastas se realizan de forma electrónica a través del Portal de Subastas del BOE.</p>
      </div>
      <div class="info-card">
        <h3>Asesoramiento Legal</h3>
        <p>Recomendamos contar con asesoramiento profesional para analizar cargas y documentación.</p>
      </div>
    </div>
  </section>

  <!-- CTA Section -->
  <section class="cta-section">
    <h2>¿Necesita Ayuda Profesional?</h2>
    <p>Nuestro equipo de expertos puede analizar las oportunidades y gestionar todo el proceso de compra.</p>
    <a href="/contacto/" class="cta-btn">Solicitar Consulta Gratuita</a>
  </section>

</div>

</body>
</html>
<!-- /wp:html -->'''

    def create_index_page(self, update_existing: bool = True) -> dict:
        """
        Crea o actualiza la página índice de subastas.

        Returns:
            Diccionario con información del resultado
        """
        slug = "subastas-judiciales"
        title = "Subastas Judiciales en España 2026 | Todas las Provincias"
        content = self.generate_index_page_content()

        # Verificar si ya existe
        existing = self._get_existing_page(slug)

        if existing and update_existing:
            response = requests.post(
                f"{self.base_url}/wp-json/wp/v2/pages/{existing['id']}",
                auth=self.auth,
                json={
                    "title": title,
                    "content": content,
                    "status": "publish"
                }
            )
            result = response.json()
            return {
                "action": "updated",
                "id": result.get("id"),
                "slug": slug,
                "url": f"{self.base_url}/{slug}/"
            }
        elif not existing:
            response = requests.post(
                f"{self.base_url}/wp-json/wp/v2/pages",
                auth=self.auth,
                json={
                    "title": title,
                    "content": content,
                    "slug": slug,
                    "status": "publish"
                }
            )
            result = response.json()
            return {
                "action": "created",
                "id": result.get("id"),
                "slug": slug,
                "url": f"{self.base_url}/{slug}/"
            }
        else:
            return {
                "action": "skipped",
                "id": existing["id"],
                "slug": slug,
                "url": f"{self.base_url}/{slug}/"
            }

    def create_all_pages(self) -> list:
        """Crea páginas para todas las 52 provincias de España."""
        results = []
        total = len(PROVINCIAS_ESPANA)
        for i, codigo in enumerate(sorted(PROVINCIAS_ESPANA.keys()), 1):
            try:
                result = self.create_page(codigo)
                results.append(result)
                print(f"  [{i}/{total}] {result['action'].upper()}: {result['provincia']} - ID: {result['id']}")
            except Exception as e:
                print(f"  [{i}/{total}] ERROR: {PROVINCIAS_ESPANA[codigo]['nombre']} - {e}")
                results.append({
                    "action": "error",
                    "id": None,
                    "provincia": PROVINCIAS_ESPANA[codigo]['nombre'],
                    "error": str(e)
                })
        return results


if __name__ == "__main__":
    generator = ProvinciaPageGenerator()
    print("═" * 60)
    print("  CREANDO PÁGINAS DE LAS 52 PROVINCIAS DE ESPAÑA")
    print("═" * 60)
    results = generator.create_all_pages()
    print("═" * 60)
    created = len([r for r in results if r['action'] == 'created'])
    updated = len([r for r in results if r['action'] == 'updated'])
    errors = len([r for r in results if r['action'] == 'error'])
    print(f"  Creadas: {created} | Actualizadas: {updated} | Errores: {errors}")
    print("═" * 60)
