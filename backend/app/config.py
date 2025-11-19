"""
Archivo de configuración para el backend de Binance.
Contiene constantes y configuraciones del sistema.
"""

import os
from datetime import datetime, timezone

# Configuración de MongoDB
MONGODB_HOST = os.getenv("MONGODB_HOST", "mongodb")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "binance_data")
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")

# Configuración del servidor Tornado
SERVER_PORT = int(os.getenv("SERVER_PORT", "8888"))

# Configuración de Binance
DEFAULT_INTERVAL = "1m"  # Intervalo de 1 minuto según requisitos

# Fecha de inicio por defecto: 1 de junio de 2025
DEFAULT_START_DATE = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
DEFAULT_START_TIMESTAMP = int(DEFAULT_START_DATE.timestamp() * 1000)

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "/logs")  # Directorio de logs compartido con Docker
