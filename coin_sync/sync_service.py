"""
Servicio de sincronización automática según condiciones.txt:
- Monitorea cada 5 segundos
- Sincroniza solo en los primeros 5 segundos del minuto
- Valida último dato en BD
- Trae datos hasta minuto actual sin segundos
- Verifica close(N-1) = open(N)
"""

import logging
import time
from datetime import datetime, timezone
from typing import List, Dict

from backend_client import BackendClient
from config import SYMBOLS_TO_SYNC

# Obtener logger
logger = logging.getLogger(__name__)


class SyncService:
    """
    Servicio que sincroniza automáticamente según condiciones especificadas.
    """

    def __init__(self, backend_client: BackendClient):
        """
        Inicializa el servicio de sincronización.

        Args:
            backend_client: Cliente para comunicarse con el backend
        """
        self.backend_client = backend_client
        self.is_running = False
        self.last_synced_minute = None  # Para evitar sincronizar el mismo minuto múltiples veces

        logger.info("Servicio de sincronización inicializado")
        logger.info("Modo: Monitoreo cada 5 segundos, sincroniza en primeros 5 segundos del minuto")

    def wait_for_backend(self, max_attempts: int = 30, wait_seconds: int = 5) -> bool:
        """
        Espera a que el backend esté disponible antes de comenzar.

        Args:
            max_attempts: Número máximo de intentos
            wait_seconds: Segundos entre intentos

        Returns:
            True si el backend está disponible, False si se agotaron los intentos
        """
        logger.info("Esperando a que el backend esté disponible...")

        for attempt in range(1, max_attempts + 1):
            if self.backend_client.health_check():
                logger.info(f"✓ Backend disponible después de {attempt} intentos")
                return True

            logger.info(f"Backend no disponible (intento {attempt}/{max_attempts}), esperando {wait_seconds}s...")
            time.sleep(wait_seconds)

        logger.error(f"✗ Backend no disponible después de {max_attempts} intentos")
        return False

    def get_symbols_to_sync(self) -> List[str]:
        """
        Obtiene la lista de símbolos a sincronizar.

        Returns:
            Lista de símbolos a sincronizar
        """
        # Si hay símbolos configurados, usarlos
        if SYMBOLS_TO_SYNC and len(SYMBOLS_TO_SYNC) > 0 and SYMBOLS_TO_SYNC[0] != '':
            return SYMBOLS_TO_SYNC

        # Si no, obtener todos los símbolos de la BD
        symbols_data = self.backend_client.get_available_symbols()

        if symbols_data is None:
            logger.warning("No se pudieron obtener símbolos del backend")
            return []

        symbols = [item["symbol"] for item in symbols_data]

        if len(symbols) == 0:
            logger.warning("No hay símbolos disponibles en la base de datos")
        else:
            logger.info(f"Se sincronizarán {len(symbols)} símbolos: {', '.join(symbols)}")

        return symbols

    def is_in_sync_window(self) -> bool:
        """
        Verifica si estamos en los primeros 5 segundos del minuto.

        Returns:
            True si estamos en segundos 0-5 del minuto actual
        """
        now = datetime.now(timezone.utc)
        seconds = now.second

        # Estamos en la ventana de sincronización si segundos está entre 0 y 5
        return 0 <= seconds <= 5

    def get_current_minute_timestamp(self) -> int:
        """
        Obtiene el timestamp del minuto actual SIN segundos.

        Returns:
            Timestamp en milisegundos del minuto actual (HH:MM:00.000)
        """
        now = datetime.now(timezone.utc)
        current_minute = now.replace(second=0, microsecond=0)
        return int(current_minute.timestamp() * 1000)

    def sync_all_symbols(self):
        """
        Sincroniza todos los símbolos disponibles.

        El backend se encarga de:
        - Verificar último minuto en BD
        - Traer todos los minutos faltantes desde último hasta minuto actual - 1
        - Insertar solo los nuevos
        - Verificar continuidad close(N-1) = open(N)
        """
        current_minute = self.get_current_minute_timestamp()

        # Evitar sincronizar el mismo minuto múltiples veces
        if self.last_synced_minute == current_minute:
            logger.debug(f"Minuto {datetime.fromtimestamp(current_minute/1000)} ya sincronizado, omitiendo")
            return

        logger.info("=" * 80)
        logger.info(f"SINCRONIZACIÓN - {datetime.fromtimestamp(current_minute/1000).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger.info("=" * 80)

        # Obtener símbolos
        symbols = self.get_symbols_to_sync()

        if len(symbols) == 0:
            logger.warning("No hay símbolos para sincronizar")
            return

        # Sincronizar cada símbolo
        successful = 0
        failed = 0

        for i, symbol in enumerate(symbols, 1):
            logger.info(f"[{i}/{len(symbols)}] Procesando {symbol}...")

            # Llamar al backend - él maneja toda la lógica:
            # 1. Valida último dato en BD
            # 2. Trae desde último+1 hasta minuto_actual-1 (solo completos)
            # 3. Verifica si ya existe antes de insertar
            # 4. Garantiza close(N-1) = open(N) porque Binance lo devuelve así
            result = self.backend_client.sync_symbol(symbol)

            if result and result.get("success"):
                new_records = result.get("new_records", 0)
                if new_records > 0:
                    logger.info(f"✓ {symbol}: {new_records} nuevos registros sincronizados")
                else:
                    logger.info(f"✓ {symbol}: Ya está al día (0 nuevos)")
                successful += 1
            else:
                logger.error(f"✗ {symbol}: Error en sincronización")
                failed += 1

            # Pausa entre símbolos
            if i < len(symbols):
                time.sleep(0.3)

        # Marcar este minuto como sincronizado
        self.last_synced_minute = current_minute

        # Resumen
        logger.info("=" * 80)
        logger.info(f"RESUMEN: {successful} exitosos, {failed} fallidos")
        logger.info("=" * 80 + "\n")

    def run(self):
        """
        Ejecuta el servicio de sincronización.

        Según condiciones.txt:
        - Monitorea cada 5 segundos con sleep(5)
        - Valida que el tiempo esté en los primeros 5 segundos del minuto
        - Si sí, trae datos desde Binance
        - Si el dato ya existe en BD, se obvia
        """
        logger.info("🚀 Iniciando servicio de sincronización")
        logger.info("📋 Condiciones:")
        logger.info("   - Monitoreo cada 5 segundos")
        logger.info("   - Sincronización en los primeros 5 segundos del minuto")
        logger.info("   - Validación de último dato en BD")
        logger.info("   - Garantía: close(N-1) = open(N)")
        logger.info("=" * 80)

        # Esperar a que el backend esté disponible
        if not self.wait_for_backend():
            logger.error("No se pudo conectar con el backend. Abortando.")
            return

        self.is_running = True
        logger.info("✓ Servicio iniciado")

        # Loop principal: monitorear cada 5 segundos
        while self.is_running:
            try:
                # Verificar si estamos en la ventana de sincronización (primeros 5 segundos)
                if self.is_in_sync_window():
                    now = datetime.now(timezone.utc)
                    logger.info(f"⏰ En ventana de sync (segundo {now.second})")

                    # Verificar que el backend siga disponible
                    if not self.backend_client.health_check():
                        logger.warning("⚠️ Backend no disponible, esperando...")
                        time.sleep(5)
                        continue

                    # Sincronizar todos los símbolos
                    self.sync_all_symbols()

                # Esperar 5 segundos antes de la próxima verificación
                time.sleep(5)

            except KeyboardInterrupt:
                logger.info("Interrupción recibida, deteniendo servicio...")
                self.stop()
                break

            except Exception as e:
                logger.error(f"❌ Error en el loop: {e}", exc_info=True)
                logger.info("Esperando 5 segundos antes de reintentar...")
                time.sleep(5)

    def stop(self):
        """Detiene el servicio de sincronización."""
        logger.info("🛑 Deteniendo servicio...")
        self.is_running = False
        logger.info("Servicio detenido")
