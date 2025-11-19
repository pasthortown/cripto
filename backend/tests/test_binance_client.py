"""
Pruebas unitarias para el cliente de Binance API.
"""

import pytest
import sys
import os

# Añadir el directorio app al path para importar los módulos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from binance_client import BinanceClient
from datetime import datetime, timezone


class TestBinanceClient:
    """
    Suite de pruebas para el cliente de Binance.
    """

    @pytest.mark.asyncio
    async def test_parse_interval_to_ms(self):
        """
        Prueba la conversión de intervalos a milisegundos.
        """
        client = BinanceClient()

        # Probar diferentes intervalos
        assert client._parse_interval_to_ms("1m") == 60 * 1000
        assert client._parse_interval_to_ms("5m") == 5 * 60 * 1000
        assert client._parse_interval_to_ms("1h") == 60 * 60 * 1000
        assert client._parse_interval_to_ms("1d") == 24 * 60 * 60 * 1000
        assert client._parse_interval_to_ms("1w") == 7 * 24 * 60 * 60 * 1000

    @pytest.mark.asyncio
    async def test_get_klines_context_manager(self):
        """
        Prueba que el cliente funciona correctamente como context manager.
        """
        async with BinanceClient() as client:
            assert client.session is not None

    @pytest.mark.asyncio
    async def test_get_klines_without_context_manager(self):
        """
        Prueba que el cliente lanza error si no se usa como context manager.
        """
        client = BinanceClient()

        with pytest.raises(RuntimeError, match="context manager"):
            await client.get_klines("BTCUSDT")

    @pytest.mark.asyncio
    async def test_get_klines_real_api(self):
        """
        Prueba real con la API de Binance (requiere conexión a internet).
        Obtiene solo 5 registros para minimizar el tiempo de prueba.
        """
        async with BinanceClient() as client:
            # Obtener 5 registros recientes de BTCUSDT
            klines = await client.get_klines(
                symbol="BTCUSDT",
                interval="1m",
                limit=5
            )

            # Verificar que se obtuvieron datos
            assert len(klines) > 0
            assert len(klines) <= 5

            # Verificar estructura de los datos
            first_kline = klines[0]
            assert "open_time" in first_kline
            assert "open" in first_kline
            assert "high" in first_kline
            assert "low" in first_kline
            assert "close" in first_kline
            assert "volume" in first_kline
            assert "close_time" in first_kline
            assert "timestamp" in first_kline

            # Verificar tipos de datos
            assert isinstance(first_kline["open"], float)
            assert isinstance(first_kline["high"], float)
            assert isinstance(first_kline["low"], float)
            assert isinstance(first_kline["close"], float)
            assert isinstance(first_kline["volume"], float)
            assert isinstance(first_kline["timestamp"], datetime)

    @pytest.mark.asyncio
    async def test_symbol_case_insensitive(self):
        """
        Prueba que el símbolo se convierte a mayúsculas automáticamente.
        """
        async with BinanceClient() as client:
            # Probar con símbolo en minúsculas
            klines = await client.get_klines(
                symbol="btcusdt",  # Minúsculas
                interval="1m",
                limit=1
            )

            # Debe funcionar correctamente
            assert len(klines) > 0
