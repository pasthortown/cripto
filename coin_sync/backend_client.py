"""
Cliente HTTP para comunicarse con el backend de Binance.
Maneja todas las peticiones al API REST del backend.
"""

import requests
import logging
from typing import List, Dict, Optional
import time

from config import BACKEND_URL, HTTP_TIMEOUT, MAX_RETRIES, RETRY_DELAY_SECONDS

# Obtener logger
logger = logging.getLogger(__name__)


class BackendClient:
    """
    Cliente para comunicarse con el backend de Binance.
    Maneja todas las peticiones HTTP al API REST.
    """

    def __init__(self, base_url: str = BACKEND_URL):
        """
        Inicializa el cliente del backend.

        Args:
            base_url: URL base del backend (ej: http://backend:8888)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = HTTP_TIMEOUT
        self.session = requests.Session()
        logger.info(f"Cliente del backend inicializado: {self.base_url}")

    def health_check(self) -> bool:
        """
        Verifica si el backend está disponible y saludable.

        Returns:
            True si el backend está disponible, False en caso contrario
        """
        try:
            url = f"{self.base_url}/health"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            is_healthy = data.get("status") == "healthy"

            if is_healthy:
                logger.info("Backend está saludable y disponible")
            else:
                logger.warning(f"Backend responde pero no está saludable: {data}")

            return is_healthy

        except requests.exceptions.RequestException as e:
            logger.error(f"Error al verificar salud del backend: {e}")
            return False

    def get_available_symbols(self) -> Optional[List[Dict]]:
        """
        Obtiene la lista de símbolos disponibles en la base de datos.

        Returns:
            Lista de diccionarios con información de símbolos, o None si hay error
        """
        try:
            url = f"{self.base_url}/api/symbols"
            logger.info("Obteniendo lista de símbolos disponibles...")

            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()

            if data.get("success"):
                symbols = data.get("symbols", [])
                logger.info(f"Se obtuvieron {len(symbols)} símbolos disponibles")
                return symbols
            else:
                logger.error(f"Error al obtener símbolos: {data}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error HTTP al obtener símbolos: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al obtener símbolos: {e}", exc_info=True)
            return None

    def sync_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Sincroniza los datos de un símbolo específico.

        Args:
            symbol: Símbolo a sincronizar (ej: BTCUSDT)

        Returns:
            Diccionario con el resultado de la sincronización, o None si hay error
        """
        url = f"{self.base_url}/api/sync"
        payload = {"symbol": symbol}

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Sincronizando {symbol} (intento {attempt}/{MAX_RETRIES})...")

                response = self.session.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()

                data = response.json()

                if data.get("success"):
                    new_records = data.get("new_records", 0)
                    stats = data.get("statistics", {})
                    total_records = stats.get("total_records", 0)

                    logger.info(
                        f"✓ {symbol} sincronizado: {new_records} nuevos registros, "
                        f"total {total_records} registros"
                    )
                    return data
                else:
                    logger.error(f"✗ Error al sincronizar {symbol}: {data}")
                    return None

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout al sincronizar {symbol} (intento {attempt}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES:
                    logger.info(f"Reintentando en {RETRY_DELAY_SECONDS} segundos...")
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    logger.error(f"✗ Falló sincronización de {symbol} después de {MAX_RETRIES} intentos")
                    return None

            except requests.exceptions.RequestException as e:
                logger.error(f"✗ Error HTTP al sincronizar {symbol}: {e}")
                if attempt < MAX_RETRIES:
                    logger.info(f"Reintentando en {RETRY_DELAY_SECONDS} segundos...")
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    return None

            except Exception as e:
                logger.error(f"✗ Error inesperado al sincronizar {symbol}: {e}", exc_info=True)
                return None

        return None

    def get_symbol_stats(self, symbol: str) -> Optional[Dict]:
        """
        Obtiene estadísticas de un símbolo.

        Args:
            symbol: Símbolo (ej: BTCUSDT)

        Returns:
            Diccionario con estadísticas, o None si hay error
        """
        try:
            url = f"{self.base_url}/api/stats/{symbol}"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()

            if data.get("success"):
                return data.get("statistics")
            else:
                logger.error(f"Error al obtener estadísticas de {symbol}: {data}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error HTTP al obtener estadísticas de {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado: {e}", exc_info=True)
            return None

    def close(self):
        """Cierra la sesión HTTP."""
        if self.session:
            self.session.close()
            logger.info("Sesión HTTP cerrada")
