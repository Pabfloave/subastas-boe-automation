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
WP_URL = os.getenv("WP_URL", "https://comprarensubasta.com")
WP_USER = os.getenv("WP_USER", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")
WP_POST_STATUS = os.getenv("WP_POST_STATUS", "publish")
# `or`: si el secreto de GitHub existe pero está vacío, getenv devuelve "".
WP_CONTACT_FORM_URL = os.getenv("WP_CONTACT_FORM_URL") or "https://comprarensubasta.com/#analisis"

# Responsable jurídico visible en fichas y páginas de provincia. Refuerza la
# autoría (E-E-A-T, citas en buscadores con IA) y cubre el art. 10 LSSI para
# profesiones reguladas (colegio y número de colegiado). Vacío = no se muestra.
AUTOR_NOMBRE = os.getenv("AUTOR_NOMBRE", "Pablo Flores Avellaneda")
AUTOR_COLEGIO = os.getenv("AUTOR_COLEGIO", "Ilustre Colegio de Abogados de Sevilla")
AUTOR_COLEGIADO = os.getenv("AUTOR_COLEGIADO", "14.408")

# Condiciones del informe jurídico previo, mostradas junto al CTA para que
# coincidan con la respuesta automática que recibe el interesado.
# Vacío = no se muestra el precio.
INFORME_PRECIO = os.getenv("INFORME_PRECIO", "72,60 € (IVA incluido)")
INFORME_PLAZO = os.getenv("INFORME_PLAZO", "24 horas hábiles")

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
