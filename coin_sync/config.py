"""
Configuración del servicio de sincronización automática de monedas.
"""

import os

# Configuración del backend
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8888")

# Configuración de sincronización
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "60"))  # 1 minuto por defecto

# Configuración de logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "/logs")

# Lista de monedas a sincronizar (vacío = todas las disponibles en BD)
# Si está vacío, se obtienen dinámicamente desde /api/symbols
SYMBOLS_TO_SYNC = os.getenv("SYMBOLS_TO_SYNC", "").split(",") if os.getenv("SYMBOLS_TO_SYNC") else []

# Timeout para requests HTTP
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "300"))  # 5 minutos

# Reintentos en caso de error
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "10"))
