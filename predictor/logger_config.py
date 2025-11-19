"""
Configuración del sistema de logging para el servicio de predicción.
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import colorlog

def setup_logger(name: str, log_dir: str = "/logs", log_level: str = "INFO"):
    """
    Configura y retorna un logger con soporte para archivos y consola.

    Args:
        name: Nombre del logger
        log_dir: Directorio donde se guardarán los logs
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Logger configurado
    """
    # Crear directorio de logs si no existe
    os.makedirs(log_dir, exist_ok=True)

    # Crear logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # Evitar duplicación de handlers
    if logger.handlers:
        return logger

    # Formato para archivos
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Formato con colores para consola
    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )

    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Handler para archivo general (rotación diaria)
    today = datetime.now().strftime('%Y-%m-%d')
    general_log_file = os.path.join(log_dir, f'predictor_{today}.txt')
    file_handler = logging.FileHandler(general_log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Handler para errores (rotación diaria)
    error_log_file = os.path.join(log_dir, f'predictor_errors_{today}.txt')
    error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(error_handler)

    return logger
