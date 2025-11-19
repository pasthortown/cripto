"""
Configuración centralizada de logging para el backend de Binance.
Los logs se escriben tanto en consola como en archivos .txt con rotación.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logging(log_level: str = "INFO", log_dir: str = "/logs"):
    """
    Configura el sistema de logging para toda la aplicación.

    Características:
    - Logs en consola (stdout) para Docker logs
    - Logs en archivo con rotación automática
    - Formato detallado con timestamp, nivel, módulo y mensaje
    - Archivos separados por tipo: general, errores

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

    # Limpiar handlers existentes para evitar duplicados
    root_logger.handlers.clear()

    # ==========================
    # Handler 1: Consola (stdout)
    # ==========================
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # ==========================
    # Handler 2: Archivo general con rotación
    # ==========================
    # Archivo: app_YYYY-MM-DD.txt
    today = datetime.now().strftime('%Y-%m-%d')
    general_log_file = os.path.join(log_dir, f"app_{today}.txt")

    # RotatingFileHandler: máximo 10 MB por archivo, mantener 5 backups
    file_handler = RotatingFileHandler(
        general_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # ==========================
    # Handler 3: Archivo solo para errores
    # ==========================
    error_log_file = os.path.join(log_dir, f"errors_{today}.txt")

    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # ==========================
    # Handler 4: Archivo para requests HTTP (opcional)
    # ==========================
    requests_log_file = os.path.join(log_dir, f"requests_{today}.txt")

    requests_handler = RotatingFileHandler(
        requests_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    requests_handler.setLevel(logging.INFO)
    requests_handler.setFormatter(formatter)

    # Aplicar este handler solo a los loggers de tornado y handlers
    tornado_logger = logging.getLogger('tornado.access')
    tornado_logger.addHandler(requests_handler)

    handlers_logger = logging.getLogger('handlers')
    handlers_logger.addHandler(requests_handler)

    # Log inicial para confirmar configuración
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("Sistema de logging configurado correctamente")
    logger.info(f"Nivel de logging: {log_level}")
    logger.info(f"Directorio de logs: {log_dir}")
    logger.info(f"Archivo general: {general_log_file}")
    logger.info(f"Archivo de errores: {error_log_file}")
    logger.info(f"Archivo de requests: {requests_log_file}")
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
