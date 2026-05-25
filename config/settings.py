"""
Configuración general del sistema de automatización de subastas BOE.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"

# Crear directorios si no existen
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# WordPress REST API
WP_URL = os.getenv("WP_URL", "https://comprarensubasta.com").rstrip("/")
WP_USER = os.getenv("WP_USER", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")
WP_POST_STATUS = os.getenv("WP_POST_STATUS", "publish")
WP_CONTACT_FORM_URL = os.getenv("WP_CONTACT_FORM_URL", f"{WP_URL}/#analisis")

# Branding (usado en schema markup, og:site_name, copy SEO, etc.)
BRAND_NAME = os.getenv("BRAND_NAME", "CAFAVE INVESTMENT")
SITE_NAME = os.getenv("SITE_NAME", "Comprar en Subasta")

# Base de datos
DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "subastas.db"))

# Scraper Settings
SELENIUM_HEADLESS = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
DELAY_BETWEEN_REQUESTS = float(os.getenv("DELAY_BETWEEN_REQUESTS", "2"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
PAGE_LOAD_TIMEOUT = int(os.getenv("PAGE_LOAD_TIMEOUT", "60"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_MAX_SIZE_MB = int(os.getenv("LOG_MAX_SIZE_MB", "10"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# URLs del BOE
BOE_BASE_URL = "https://subastas.boe.es"
BOE_SEARCH_URL = f"{BOE_BASE_URL}/subastas_ava.php"
BOE_DETAIL_URL = f"{BOE_BASE_URL}/detalleSubasta.php"

# Provincias a monitorear
# Por defecto: TODAS las 52 provincias de España
# Códigos INE: 01-50 + 51 (Ceuta) + 52 (Melilla)
TODAS_LAS_PROVINCIAS = ",".join([f"{i:02d}" for i in range(1, 53)])
PROVINCIAS_STR = os.getenv("PROVINCIAS", TODAS_LAS_PROVINCIAS)
PROVINCIAS_CODIGOS = [p.strip() for p in PROVINCIAS_STR.split(",")]
