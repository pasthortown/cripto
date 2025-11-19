"""
Servicio de sincronización en tiempo real minuto a minuto.
Se ejecuta al inicio de cada minuto (segundo 0) y obtiene la vela del minuto anterior.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List
from binance_client import BinanceClient
from db_client import MongoDBClient
from websocket_manager import connection_manager
from config import (
    MONGODB_HOST, MONGODB_PORT, MONGODB_DATABASE,
    MONGODB_USERNAME, MONGODB_PASSWORD, DEFAULT_INTERVAL
)
from logger_config import setup_logging, get_logger

# Configurar logging
setup_logging(log_level="INFO", log_dir="/logs")
logger = get_logger(__name__)


class RealTimeSyncService:
    """
    Servicio que sincroniza datos de Binance cada minuto exacto.

    Características:
    - Se ejecuta en el segundo 0 de cada minuto
    - Obtiene la vela del minuto ANTERIOR (completa)
    - Garantiza continuidad: close(N-1) = open(N)
    - Sin gaps, sin sleep aleatorio
    """

    def __init__(self, symbols: List[str]):
        """
        Inicializa el servicio de sincronización.

        Args:
            symbols: Lista de símbolos a sincronizar (ej: ['BTCUSDT', 'ETHUSDT'])
        """
        self.symbols = [s.upper() for s in symbols]
        self.db_client = None
        self.running = False

    async def connect(self):
        """Conecta a MongoDB."""
        self.db_client = MongoDBClient(
            host=MONGODB_HOST,
            port=MONGODB_PORT,
            database=MONGODB_DATABASE,
            username=MONGODB_USERNAME,
            password=MONGODB_PASSWORD
        )
        await self.db_client.connect()
        logger.info("✓ Conectado a MongoDB")

    async def disconnect(self):
        """Desconecta de MongoDB."""
        if self.db_client:
            await self.db_client.close()
            logger.info("✓ Desconectado de MongoDB")

    def _get_next_minute_boundary(self) -> datetime:
        """
        Calcula el próximo minuto exacto (segundo 0).

        Returns:
            Datetime del próximo minuto en punto
        """
        now = datetime.now(timezone.utc)
        # Siguiente minuto = ahora + 1 minuto, con segundos = 0
        next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        return next_minute

    def _get_previous_minute_range(self) -> tuple[int, int]:
        """
        Obtiene el rango del minuto ANTERIOR (ya completo).

        Returns:
            Tupla (start_time_ms, end_time_ms) del minuto anterior
        """
        now = datetime.now(timezone.utc)
        # Minuto anterior = ahora - 1 minuto
        previous_minute = now.replace(second=0, microsecond=0) - timedelta(minutes=1)

        # Inicio del minuto: HH:MM:00.000
        start_time = previous_minute
        # Fin del minuto: HH:MM:59.999
        end_time = previous_minute.replace(second=59, microsecond=999999)

        # Convertir a milisegundos
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        return start_ms, end_ms

    async def _wait_until_next_minute(self):
        """
        Espera hasta el próximo minuto exacto (segundo 0).
        Usa cálculo preciso sin sleep fijo.
        """
        next_minute = self._get_next_minute_boundary()
        now = datetime.now(timezone.utc)

        # Calcular cuántos segundos faltan
        wait_seconds = (next_minute - now).total_seconds()

        if wait_seconds > 0:
            logger.info(f"⏳ Esperando {wait_seconds:.2f}s hasta {next_minute.strftime('%H:%M:%S')}")
            await asyncio.sleep(wait_seconds)

    async def sync_symbol(self, symbol: str) -> dict:
        """
        Sincroniza un símbolo: obtiene la vela del minuto anterior.

        Args:
            symbol: Símbolo a sincronizar

        Returns:
            Diccionario con resultado de la sincronización
        """
        try:
            # Obtener el rango del minuto anterior (completo)
            start_ms, end_ms = self._get_previous_minute_range()

            start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)

            logger.info(f"📊 {symbol}: Obteniendo vela {start_dt.strftime('%H:%M:%S')} - {end_dt.strftime('%H:%M:%S')}")

            # Obtener datos de Binance (solo 1 vela)
            async with BinanceClient() as binance_client:
                klines = await binance_client.get_klines(
                    symbol=symbol,
                    interval=DEFAULT_INTERVAL,
                    start_time=start_ms,
                    end_time=end_ms,
                    limit=1  # Solo 1 vela
                )

            if not klines or len(klines) == 0:
                logger.warning(f"⚠️  {symbol}: No se obtuvo vela para {start_dt.strftime('%H:%M')}")
                return {
                    "symbol": symbol,
                    "success": False,
                    "message": "No data from Binance"
                }

            # Verificar que la vela sea del minuto correcto
            kline = klines[0]
            if kline["open_time"] != start_ms:
                logger.warning(f"⚠️  {symbol}: Vela con timestamp incorrecto. Esperado: {start_ms}, Recibido: {kline['open_time']}")
                return {
                    "symbol": symbol,
                    "success": False,
                    "message": "Incorrect timestamp"
                }

            # Verificar si ya existe en la BD (evitar duplicados)
            existing = await self.db_client.get_klines(
                symbol=symbol,
                start_time=start_ms,
                end_time=start_ms,
                limit=1
            )

            if existing and len(existing) > 0:
                logger.info(f"ℹ️  {symbol}: Vela ya existe en BD para {start_dt.strftime('%H:%M')}")
                return {
                    "symbol": symbol,
                    "success": True,
                    "message": "Already exists",
                    "price": kline["close"]
                }

            # Guardar en MongoDB
            inserted_count = await self.db_client.insert_klines(symbol, klines)

            if inserted_count > 0:
                logger.info(f"✓ {symbol}: Vela guardada - Close: ${kline['close']:.2f}")

                # Notificar a clientes WebSocket
                stats = await self.db_client.get_statistics(symbol)
                connection_manager.notify_sync_complete(symbol, {
                    "new_records": 1,
                    "total_records": stats.get("total_records", 0),
                    "last_price": kline["close"],
                    "last_record": start_dt.isoformat()
                })

                return {
                    "symbol": symbol,
                    "success": True,
                    "message": "Inserted",
                    "price": kline["close"]
                }
            else:
                logger.warning(f"⚠️  {symbol}: No se pudo guardar la vela")
                return {
                    "symbol": symbol,
                    "success": False,
                    "message": "Insert failed"
                }

        except Exception as e:
            logger.error(f"❌ {symbol}: Error en sincronización - {e}", exc_info=True)
            return {
                "symbol": symbol,
                "success": False,
                "message": str(e)
            }

    async def sync_all_symbols(self):
        """
        Sincroniza todos los símbolos configurados en paralelo.
        """
        now = datetime.now(timezone.utc)
        logger.info(f"\n{'='*80}")
        logger.info(f"🔄 Sincronización minuto: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger.info(f"{'='*80}")

        # Ejecutar sincronización de todos los símbolos en paralelo
        tasks = [self.sync_symbol(symbol) for symbol in self.symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Resumen
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        logger.info(f"\n✓ Sincronización completada: {success_count}/{len(self.symbols)} símbolos")
        logger.info(f"{'='*80}\n")

    async def run(self):
        """
        Ejecuta el servicio de sincronización continua.
        Se ejecuta en el segundo 0 de cada minuto.
        """
        self.running = True
        logger.info("🚀 Servicio de sincronización en tiempo real iniciado")
        logger.info(f"📊 Símbolos: {', '.join(self.symbols)}")
        logger.info(f"⏰ Frecuencia: Cada minuto exacto (segundo 0)")
        logger.info("="*80)

        try:
            # Conectar a MongoDB
            await self.connect()

            # Esperar hasta el próximo minuto para empezar sincronizado
            logger.info("⏳ Esperando hasta el próximo minuto para empezar...")
            await self._wait_until_next_minute()

            # Bucle principal
            while self.running:
                # Sincronizar todos los símbolos
                await self.sync_all_symbols()

                # Esperar hasta el próximo minuto exacto
                await self._wait_until_next_minute()

        except KeyboardInterrupt:
            logger.info("\n⏹️  Interrupción de usuario detectada")
        except Exception as e:
            logger.error(f"❌ Error fatal en servicio: {e}", exc_info=True)
        finally:
            self.running = False
            await self.disconnect()
            logger.info("👋 Servicio de sincronización detenido")

    def stop(self):
        """Detiene el servicio."""
        self.running = False


async def main():
    """
    Función principal para ejecutar el servicio.
    """
    # Lista de símbolos a sincronizar
    SYMBOLS = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "ADAUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "DOTUSDT",
        "DOGEUSDT",
        "MATICUSDT",
        "LTCUSDT"
    ]

    # Crear y ejecutar servicio
    service = RealTimeSyncService(symbols=SYMBOLS)

    try:
        await service.run()
    except KeyboardInterrupt:
        logger.info("Deteniendo servicio...")
        service.stop()


if __name__ == "__main__":
    asyncio.run(main())
