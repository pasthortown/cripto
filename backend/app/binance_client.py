"""
Cliente para interactuar con la API pública de Binance.
Permite obtener datos históricos de klines (velas) para diferentes pares de trading.
"""

import aiohttp
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging

# Obtener logger
logger = logging.getLogger(__name__)


class BinanceClient:
    """
    Cliente asíncrono para consumir datos de Binance API.
    Utiliza la API pública que no requiere autenticación.
    """

    BASE_URL = "https://api.binance.com"
    KLINES_ENDPOINT = "/api/v3/klines"

    def __init__(self):
        """Inicializa el cliente de Binance."""
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Context manager para inicializar la sesión HTTP."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager para cerrar la sesión HTTP."""
        if self.session:
            await self.session.close()

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1m",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """
        Obtiene datos de klines (velas) de Binance.

        Args:
            symbol: Par de trading (ej: BTCUSDT)
            interval: Intervalo de tiempo (1m, 5m, 15m, 1h, etc.)
            start_time: Timestamp en milisegundos desde cuando buscar
            end_time: Timestamp en milisegundos hasta cuando buscar
            limit: Cantidad máxima de registros (máx: 1000)

        Returns:
            Lista de diccionarios con los datos de las velas
        """
        if not self.session:
            raise RuntimeError("El cliente debe usarse como context manager (async with)")

        # Construir parámetros de la consulta
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, 1000)  # Binance limita a 1000 por request
        }

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        url = f"{self.BASE_URL}{self.KLINES_ENDPOINT}"

        try:
            logger.info(f"Solicitando datos de {symbol} desde Binance API")
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

                # Transformar los datos de Binance a un formato más legible
                klines = []
                for item in data:
                    kline = {
                        "open_time": item[0],
                        "open": float(item[1]),
                        "high": float(item[2]),
                        "low": float(item[3]),
                        "close": float(item[4]),
                        "volume": float(item[5]),
                        "close_time": item[6],
                        "quote_asset_volume": float(item[7]),
                        "number_of_trades": item[8],
                        "taker_buy_base_asset_volume": float(item[9]),
                        "taker_buy_quote_asset_volume": float(item[10]),
                        "timestamp": datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc)
                    }
                    klines.append(kline)

                logger.info(f"Se obtuvieron {len(klines)} registros de {symbol}")
                return klines

        except aiohttp.ClientError as e:
            logger.error(f"Error al consultar Binance API: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            raise

    async def get_all_klines_in_range(
        self,
        symbol: str,
        start_time: int,
        end_time: int,
        interval: str = "1m"
    ) -> List[Dict]:
        """
        Obtiene todos los klines en un rango de tiempo, manejando el límite de 1000 por request.

        Args:
            symbol: Par de trading (ej: BTCUSDT)
            start_time: Timestamp en milisegundos desde cuando buscar
            end_time: Timestamp en milisegundos hasta cuando buscar
            interval: Intervalo de tiempo (1m, 5m, 15m, 1h, etc.)

        Returns:
            Lista completa de klines en el rango especificado
        """
        all_klines = []
        current_start = start_time

        # Duración de un intervalo en milisegundos (para 1m = 60000ms)
        interval_ms = self._parse_interval_to_ms(interval)

        logger.info(f"Obteniendo datos de {symbol} desde {datetime.fromtimestamp(start_time/1000)} hasta {datetime.fromtimestamp(end_time/1000)}")

        while current_start < end_time:
            # Obtener un lote de datos
            klines = await self.get_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=end_time,
                limit=1000
            )

            if not klines:
                break

            all_klines.extend(klines)

            # Actualizar el tiempo de inicio para el siguiente lote
            # Usar el close_time del último kline + 1ms
            current_start = klines[-1]["close_time"] + 1

            # Pequeña pausa para no saturar la API
            await asyncio.sleep(0.1)

        logger.info(f"Total de registros obtenidos: {len(all_klines)}")
        return all_klines

    def _parse_interval_to_ms(self, interval: str) -> int:
        """
        Convierte un intervalo de string a milisegundos.

        Args:
            interval: Intervalo en formato string (1m, 5m, 1h, etc.)

        Returns:
            Milisegundos correspondientes al intervalo
        """
        unit = interval[-1]
        value = int(interval[:-1])

        if unit == 'm':
            return value * 60 * 1000
        elif unit == 'h':
            return value * 60 * 60 * 1000
        elif unit == 'd':
            return value * 24 * 60 * 60 * 1000
        elif unit == 'w':
            return value * 7 * 24 * 60 * 60 * 1000
        else:
            return 60 * 1000  # Default: 1 minuto
