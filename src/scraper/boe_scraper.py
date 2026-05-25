"""
Scraper principal para el portal de subastas del BOE.
Utiliza Selenium para navegar y extraer datos de subastas.boe.es
"""
import time
import tempfile
import logging
from typing import List, Optional, Dict, Generator
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from .parser import SubastaParser
from ..models.subasta import Subasta, Bien

# Configuración importada
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import settings


logger = logging.getLogger(__name__)

# Tope duro de tiempo por provincia en buscar_subastas(). Si la paginación del BOE
# rompe (_ir_siguiente_pagina devuelve True falsamente), el bucle iteraría
# max_paginas × delay segundos sin avanzar. Esto lo corta a tiempo.
MAX_SEARCH_DURATION_SECONDS = 120


class BOEScraper:
    """
    Scraper para el portal de subastas del BOE.
    Utiliza Selenium para navegar por páginas dinámicas.
    """

    def __init__(self, headless: bool = True):
        """
        Inicializa el scraper.

        Args:
            headless: Si True, ejecuta Chrome sin interfaz gráfica
        """
        self.headless = headless
        self.driver = None
        self.parser = SubastaParser()
        self.base_url = settings.BOE_BASE_URL
        self.search_url = settings.BOE_SEARCH_URL
        self.detail_url = settings.BOE_DETAIL_URL
        self.timeout = settings.REQUEST_TIMEOUT
        self.delay = settings.DELAY_BETWEEN_REQUESTS

    def _init_driver(self):
        """Inicializa el WebDriver de Chrome."""
        if self.driver is not None:
            return

        options = Options()
        if self.headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(settings.PAGE_LOAD_TIMEOUT)
            logger.info("WebDriver de Chrome inicializado correctamente")
        except Exception as e:
            logger.error(f"Error inicializando WebDriver: {e}")
            raise

    def close(self):
        """Cierra el WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("WebDriver cerrado")

    def __enter__(self):
        """Context manager entry."""
        self._init_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def buscar_subastas(
        self,
        provincia: str,
        tipo_bien: str = "I",
        estado: str = "EJ",
        max_paginas: int = 100
    ) -> Generator[Dict, None, None]:
        """
        Busca subastas por provincia y otros criterios.

        Args:
            provincia: Código de provincia (ej: "41" para Sevilla)
            tipo_bien: "I" para inmuebles, "V" para vehículos
            estado: "EJ" celebrándose, "PU" próximas
            max_paginas: Número máximo de páginas a procesar

        Yields:
            Diccionarios con información básica de cada subasta encontrada
        """
        self._init_driver()

        logger.info(f"Buscando subastas en provincia {provincia}")

        try:
            # Navegar al formulario de búsqueda avanzada
            self.driver.get(self.search_url)
            self._wait_for_page_load()
            time.sleep(self.delay)

            # Rellenar el formulario usando JavaScript para evitar problemas de click interceptado
            # Seleccionar estado de subasta (Celebrándose)
            if estado:
                estado_radio_id = f"idEstado{estado}"
                try:
                    self.driver.execute_script(f"document.getElementById('{estado_radio_id}').click();")
                    time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"No se pudo seleccionar estado {estado}: {e}")

            # Seleccionar tipo de bien (Inmuebles)
            if tipo_bien:
                tipo_bien_id = f"idTipoBien{tipo_bien}"
                try:
                    self.driver.execute_script(f"document.getElementById('{tipo_bien_id}').click();")
                    time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"No se pudo seleccionar tipo {tipo_bien}: {e}")

            # Seleccionar provincia
            if provincia:
                try:
                    self.driver.execute_script(f"""
                        var select = document.getElementById('BIEN.COD_PROVINCIA');
                        select.value = '{provincia}';
                        select.dispatchEvent(new Event('change'));
                    """)
                    time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"No se pudo seleccionar provincia: {e}")

            # Click en el botón de búsqueda
            try:
                self.driver.execute_script("""
                    var buttons = document.querySelectorAll('input[type="submit"][value="Buscar"]');
                    if (buttons.length > 0) {
                        buttons[0].click();
                    } else {
                        document.forms[0].submit();
                    }
                """)
            except Exception as e:
                logger.error(f"Error enviando formulario: {e}")

            self._wait_for_page_load()
            time.sleep(self.delay)

            start_time = time.time()
            pagina = 1
            while pagina <= max_paginas:
                elapsed = time.time() - start_time
                if elapsed > MAX_SEARCH_DURATION_SECONDS:
                    logger.warning(
                        f"Timeout absoluto alcanzado ({elapsed:.1f}s > "
                        f"{MAX_SEARCH_DURATION_SECONDS}s) en provincia {provincia} "
                        f"tras {pagina - 1} páginas — abortando paginación"
                    )
                    break

                logger.info(f"Procesando página {pagina} de resultados")

                # Obtener HTML de la página actual
                html = self.driver.page_source

                # Debug: guardar HTML para análisis
                logger.debug(f"URL actual: {self.driver.current_url}")
                logger.debug(f"Título de página: {self.driver.title}")

                # Verificar si hay error en la página
                if "ERROR" in html or "error" in html.lower():
                    logger.warning("Posible error en la página de resultados")
                    # Guardar para debug — archivo único por thread/provincia para evitar
                    # sobrescritura cuando varios scrapers corren en paralelo (GH Actions matrix)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    prefix = f"boe_debug_{provincia}_{timestamp}_"
                    with tempfile.NamedTemporaryFile(
                        mode="w", encoding="utf-8", suffix=".html",
                        prefix=prefix, delete=False
                    ) as f:
                        f.write(html)
                        debug_path = f.name
                    logger.info(f"HTML guardado en {debug_path} para depuración")

                # Parsear listado
                subastas_en_pagina = self._extraer_subastas_de_listado(html)

                if not subastas_en_pagina:
                    logger.info("No se encontraron más subastas en esta página")
                    break

                for subasta_info in subastas_en_pagina:
                    yield subasta_info

                # Intentar ir a la siguiente página
                if not self._ir_siguiente_pagina():
                    logger.info("No hay más páginas de resultados")
                    break

                pagina += 1
                time.sleep(self.delay)

        except TimeoutException:
            logger.error("Timeout al cargar página de búsqueda")
        except Exception as e:
            logger.error(f"Error en búsqueda de subastas: {e}")

    def _extraer_subastas_de_listado(self, html: str) -> List[Dict]:
        """Extrae información de subastas del HTML del listado."""
        subastas = []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Buscar elementos que contienen información de subastas
        # El BOE puede usar diferentes estructuras, intentamos varias

        # Método 1: Buscar por enlaces con idSub
        import re
        enlaces = soup.select("a[href*='idSub=']")
        ids_procesados = set()

        for enlace in enlaces:
            href = enlace.get("href", "")

            # Extraer ID de subasta (formato: SUB-XX-YYYY-NNNNNN)
            match = re.search(r"idSub=(SUB-[A-Z]{2}-\d{4}-[A-Z0-9]+)", href)
            if not match:
                # Intentar formato alternativo
                match = re.search(r"idSub=([A-Z0-9-]+?)(?:&|$)", href)
                if not match:
                    continue

            id_subasta = match.group(1)
            if id_subasta in ids_procesados:
                continue
            ids_procesados.add(id_subasta)

            # Construir URL de detalle (sin el parámetro idBus)
            subasta_info = {
                "id_subasta": id_subasta,
                "url_detalle": f"{self.detail_url}?idSub={id_subasta}",
            }

            # Buscar el contenedor padre para más datos
            parent = enlace.find_parent("tr") or enlace.find_parent("div", class_=re.compile(r"resultado|subasta|caja"))
            if parent:
                # Intentar extraer valor, estado, etc.
                texto = parent.get_text(" ", strip=True)

                # Buscar valor monetario
                valor_match = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:EUR|€)", texto)
                if valor_match:
                    subasta_info["valor_texto"] = valor_match.group(1)

            subastas.append(subasta_info)

        logger.info(f"Encontradas {len(subastas)} subastas en el listado")
        return subastas

    def _ir_siguiente_pagina(self) -> bool:
        """
        Intenta navegar a la siguiente página de resultados.

        Returns:
            True si se navegó exitosamente, False si no hay más páginas
        """
        try:
            # Buscar enlace de siguiente página
            siguiente = self.driver.find_elements(
                By.XPATH,
                "//a[contains(@class, 'siguiente') or contains(text(), 'Siguiente') or contains(text(), '»')]"
            )

            if siguiente:
                siguiente[0].click()
                self._wait_for_page_load()
                time.sleep(self.delay)
                return True

            # Buscar por paginación numérica
            paginas = self.driver.find_elements(By.CSS_SELECTOR, ".paginacion a, .pagination a")
            current_page = None
            for elem in paginas:
                if "active" in elem.get_attribute("class") or "current" in elem.get_attribute("class"):
                    current_page = elem
                    break

            if current_page:
                next_sibling = current_page.find_element(By.XPATH, "following-sibling::a")
                if next_sibling:
                    next_sibling.click()
                    self._wait_for_page_load()
                    time.sleep(self.delay)
                    return True

        except (NoSuchElementException, Exception) as e:
            logger.debug(f"No se pudo navegar a la siguiente página: {e}")

        return False

    def get_detalle_subasta(self, id_subasta: str) -> Optional[Subasta]:
        """
        Obtiene el detalle completo de una subasta.

        Args:
            id_subasta: Identificador de la subasta (ej: SUB-JA-2025-249514)

        Returns:
            Objeto Subasta con toda la información, o None si hay error
        """
        self._init_driver()

        logger.info(f"Obteniendo detalle de subasta {id_subasta}")

        try:
            # Pestaña 1: Información general
            url_general = f"{self.detail_url}?idSub={id_subasta}&ver=1"
            self.driver.get(url_general)
            self._wait_for_page_load()
            time.sleep(self.delay)

            html_general = self.driver.page_source
            datos_generales = self.parser.parse_detalle_general(html_general)
            datos_generales["id_subasta"] = id_subasta
            datos_generales["url_detalle"] = url_general

            # Pestaña 2: Autoridad gestora
            url_autoridad = f"{self.detail_url}?idSub={id_subasta}&ver=2"
            self.driver.get(url_autoridad)
            self._wait_for_page_load()
            time.sleep(self.delay)

            html_autoridad = self.driver.page_source
            datos_autoridad = self.parser.parse_autoridad_gestora(html_autoridad)

            # Pestaña 3: Bienes - Primero cargar página principal para detectar lotes
            url_bienes = f"{self.detail_url}?idSub={id_subasta}&ver=3"
            self.driver.get(url_bienes)
            self._wait_for_page_load()
            time.sleep(self.delay)

            html_bienes = self.driver.page_source

            # Detectar si hay múltiples lotes buscando enlaces Lote1, Lote2, etc.
            from bs4 import BeautifulSoup
            import re
            soup = BeautifulSoup(html_bienes, 'lxml')

            # Buscar enlaces de lotes individuales (ej: idLote=1, idLote=2)
            lote_links = soup.select('a[href*="idLote="]')
            lote_numbers = set()
            for link in lote_links:
                href = link.get('href', '')
                match = re.search(r'idLote=(\d+)', href)
                if match:
                    lote_numbers.add(int(match.group(1)))

            bienes = []

            if lote_numbers:
                # Hay múltiples lotes - cargar cada uno individualmente
                logger.info(f"Detectados {len(lote_numbers)} lotes para {id_subasta}")
                for lote_num in sorted(lote_numbers):
                    url_lote = f"{self.detail_url}?idSub={id_subasta}&ver=3&idLote={lote_num}"
                    self.driver.get(url_lote)
                    self._wait_for_page_load()
                    time.sleep(self.delay / 2)  # Delay más corto entre lotes

                    html_lote = self.driver.page_source
                    lote_bienes = self.parser.parse_detalle_bienes(html_lote, id_subasta)

                    # Asignar número de lote correcto
                    for bien in lote_bienes:
                        bien.numero_bien = lote_num

                    bienes.extend(lote_bienes)
                    logger.debug(f"Lote {lote_num}: {len(lote_bienes)} bienes extraídos")
            else:
                # Solo un lote o estructura diferente - usar método original
                bienes = self.parser.parse_detalle_bienes(html_bienes, id_subasta)

            # Crear objeto Subasta
            subasta = self.parser.crear_subasta_desde_detalle(
                datos_generales,
                bienes,
                datos_autoridad
            )

            logger.info(f"Subasta {id_subasta} extraída: {len(bienes)} bienes")
            return subasta

        except TimeoutException:
            logger.error(f"Timeout al cargar detalle de subasta {id_subasta}")
        except Exception as e:
            logger.error(f"Error obteniendo detalle de {id_subasta}: {e}")

        return None

    def _wait_for_page_load(self, timeout: int = None):
        """Espera a que la página cargue completamente."""
        timeout = timeout or self.timeout
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            logger.warning("Timeout esperando carga de página")

    def verificar_conexion(self) -> bool:
        """
        Verifica que se puede conectar al portal del BOE.

        Returns:
            True si la conexión es exitosa
        """
        self._init_driver()

        try:
            self.driver.get(self.base_url)
            self._wait_for_page_load()

            # Verificar que la página cargó correctamente
            if "subastas" in self.driver.title.lower() or "boe" in self.driver.title.lower():
                logger.info("Conexión al BOE verificada correctamente")
                return True
            else:
                logger.warning(f"Página cargada pero título inesperado: {self.driver.title}")
                return True  # La página cargó, aunque el título sea diferente

        except Exception as e:
            logger.error(f"Error verificando conexión al BOE: {e}")
            return False


def scrape_provincia(
    provincia: str,
    db=None,
    wp_publisher=None,
    dry_run: bool = False,
    limit: int = None
) -> Dict:
    """
    Función de alto nivel para hacer scraping de una provincia completa.

    Args:
        provincia: Código de provincia
        db: Instancia de Database (opcional)
        wp_publisher: Instancia de WordPressPublisher (opcional)
        dry_run: Si True, no guarda ni publica
        limit: Límite de subastas a procesar

    Returns:
        Diccionario con estadísticas
    """
    stats = {
        "encontradas": 0,
        "nuevas": 0,
        "actualizadas": 0,
        "publicadas": 0,
        "errores": 0,
    }

    with BOEScraper(headless=settings.SELENIUM_HEADLESS) as scraper:
        count = 0

        for subasta_info in scraper.buscar_subastas(provincia=provincia):
            if limit and count >= limit:
                break

            stats["encontradas"] += 1
            id_subasta = subasta_info.get("id_subasta")

            if not id_subasta:
                continue

            try:
                # Verificar si existe en BD
                existe = db.subasta_existe(id_subasta) if db else False

                # Obtener detalle completo
                subasta = scraper.get_detalle_subasta(id_subasta)
                if not subasta:
                    stats["errores"] += 1
                    continue

                if not dry_run:
                    if db:
                        if existe:
                            db.update_subasta(subasta)
                            stats["actualizadas"] += 1
                        else:
                            db.insert_subasta(subasta)
                            stats["nuevas"] += 1

                    if wp_publisher and not existe:
                        try:
                            post_id = wp_publisher.publish_subasta(subasta)
                            if db:
                                db.update_wp_post_id(id_subasta, post_id)
                            stats["publicadas"] += 1
                        except Exception as e:
                            logger.error(f"Error publicando {id_subasta}: {e}")
                            stats["errores"] += 1

                count += 1
                logger.info(f"Procesada subasta {count}: {id_subasta}")

            except Exception as e:
                logger.error(f"Error procesando subasta {id_subasta}: {e}")
                stats["errores"] += 1

    return stats
