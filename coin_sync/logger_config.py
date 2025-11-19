"""
Configuración de logging para el servicio de sincronización.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logging(log_level: str = "INFO", log_dir: str = "/logs"):
    """
    Configura el sistema de logging para el servicio de sincronización.

    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directorio donde se guardarán los archivos de log
    """

    # Crear directorio de logs si no existe
    os.makedirs(log_dir, exist_ok=True)

    # Convertir string de nivel a constante de logging
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Formato detallado de los logs
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Obtener el logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Limpiar handlers existentes
    root_logger.handlers.clear()

    # ==========================
    # Handler 1: Consola (stdout)
    # ==========================
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # ==========================
    # Handler 2: Archivo de sync
    # ==========================
    today = datetime.now().strftime('%Y-%m-%d')
    sync_log_file = os.path.join(log_dir, f"coin_sync_{today}.txt")

    file_handler = RotatingFileHandler(
        sync_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # ==========================
    # Handler 3: Archivo de errores
    # ==========================
    error_log_file = os.path.join(log_dir, f"coin_sync_errors_{today}.txt")

    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # Log inicial
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("Sistema de logging de coin_sync configurado")
    logger.info(f"Nivel de logging: {log_level}")
    logger.info(f"Directorio de logs: {log_dir}")
    logger.info(f"Archivo de sync: {sync_log_file}")
    logger.info(f"Archivo de errores: {error_log_file}")
    logger.info("=" * 80)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger con el nombre especificado.

    Args:
        name: Nombre del logger (normalmente __name__ del módulo)

    Returns:
        Logger configurado
    """
    return logging.getLogger(name)
