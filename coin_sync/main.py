"""
Punto de entrada del servicio de sincronización automática de monedas.
"""

import logging
import signal
import sys

from logger_config import setup_logging, get_logger
from backend_client import BackendClient
from sync_service import SyncService
from config import LOG_LEVEL, LOG_DIR, BACKEND_URL, SYNC_INTERVAL_SECONDS


# Variable global para el servicio (para poder detenerlo en signal handler)
sync_service = None


def signal_handler(sig, frame):
    """
    Maneja las señales de terminación (SIGINT, SIGTERM).
    Detiene el servicio de forma limpia.
    """
    logger = get_logger(__name__)
    logger.info(f"Señal {sig} recibida, deteniendo servicio...")

    if sync_service:
        sync_service.stop()

    sys.exit(0)


def main():
    """
    Función principal del servicio de sincronización.
    """
    # Configurar logging
    setup_logging(log_level=LOG_LEVEL, log_dir=LOG_DIR)
    logger = get_logger(__name__)

    logger.info("=" * 80)
    logger.info("SERVICIO DE SINCRONIZACIÓN AUTOMÁTICA DE MONEDAS")
    logger.info("=" * 80)
    logger.info(f"Backend URL: {BACKEND_URL}")
    logger.info(f"Intervalo de sincronización: {SYNC_INTERVAL_SECONDS} segundos")
    logger.info(f"Nivel de logging: {LOG_LEVEL}")
    logger.info(f"Directorio de logs: {LOG_DIR}")
    logger.info("=" * 80)

    # Registrar handlers de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Inicializar cliente del backend
        backend_client = BackendClient(base_url=BACKEND_URL)

        # Inicializar servicio de sincronización
        global sync_service
        sync_service = SyncService(backend_client)

        # Ejecutar servicio (loop infinito)
        sync_service.run()

    except Exception as e:
        logger.error(f"Error fatal en el servicio: {e}", exc_info=True)
        sys.exit(1)

    finally:
        logger.info("Servicio finalizado")


if __name__ == "__main__":
    main()
