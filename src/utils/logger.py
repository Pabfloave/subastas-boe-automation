"""
Sistema de logging para el proyecto.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime

# Importar configuración
import os
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import settings


def setup_logger(
    name: str,
    log_file: str = None,
    level: str = None,
    max_bytes: int = None,
    backup_count: int = None
) -> logging.Logger:
    """
    Configura un logger con salida a consola y archivo.

    Args:
        name: Nombre del logger
        log_file: Ruta al archivo de log (opcional)
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR)
        max_bytes: Tamaño máximo del archivo antes de rotar
        backup_count: Número de archivos de backup a mantener

    Returns:
        Logger configurado
    """
    level = level or settings.LOG_LEVEL
    max_bytes = max_bytes or (settings.LOG_MAX_SIZE_MB * 1024 * 1024)
    backup_count = backup_count or settings.LOG_BACKUP_COUNT

    logger = logging.getLogger(name)

    # Evitar duplicación de handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Formato del log
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # Handler para archivo (si se especifica o por defecto)
    if log_file is None:
        settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = settings.LOG_DIR / f"{name}_{datetime.now().strftime('%Y%m')}.log"

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, level.upper(), logging.DEBUG))
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene o crea un logger.

    Args:
        name: Nombre del logger

    Returns:
        Logger configurado
    """
    return setup_logger(name)


# Loggers predefinidos
def get_scraper_logger() -> logging.Logger:
    """Logger para el módulo de scraping."""
    return setup_logger('scraper')


def get_wordpress_logger() -> logging.Logger:
    """Logger para el módulo de WordPress."""
    return setup_logger('wordpress')


def get_database_logger() -> logging.Logger:
    """Logger para el módulo de base de datos."""
    return setup_logger('database')


def get_sync_logger() -> logging.Logger:
    """Logger para sincronización."""
    return setup_logger('sync')


class LogCapture:
    """Contexto para capturar logs en una lista."""

    def __init__(self, logger_name: str = None):
        self.logger_name = logger_name
        self.logs = []
        self.handler = None

    def __enter__(self):
        class ListHandler(logging.Handler):
            def __init__(self, logs_list):
                super().__init__()
                self.logs_list = logs_list

            def emit(self, record):
                self.logs_list.append({
                    'level': record.levelname,
                    'message': record.getMessage(),
                    'time': datetime.fromtimestamp(record.created),
                })

        logger = logging.getLogger(self.logger_name)
        self.handler = ListHandler(self.logs)
        logger.addHandler(self.handler)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.handler:
            logger = logging.getLogger(self.logger_name)
            logger.removeHandler(self.handler)
