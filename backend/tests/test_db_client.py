"""
Pruebas unitarias para el cliente de MongoDB.
Estas pruebas requieren una instancia de MongoDB corriendo.
"""

import pytest
import sys
import os
from datetime import datetime, timezone

# Añadir el directorio app al path para importar los módulos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from db_client import MongoDBClient


# Marcador para pruebas que requieren MongoDB
pytestmark = pytest.mark.asyncio


class TestMongoDBClient:
    """
    Suite de pruebas para el cliente de MongoDB.
    """

    @pytest.fixture
    async def db_client(self):
        """
        Fixture que crea un cliente de MongoDB para testing.
        Usa una base de datos de prueba que se limpia después.
        """
        # Obtener credenciales de variables de entorno o usar las del .env
        username = os.getenv("MONGODB_ROOT_USERNAME", "admin")
        password = os.getenv("MONGODB_ROOT_PASSWORD", "SecurePass123!")

        # Crear cliente con base de datos de prueba
        client = MongoDBClient(
            host="localhost",
            port=21018,  # Puerto expuesto en docker-compose
            database="binance_test",
            username=username,
            password=password
        )

        try:
            await client.connect()
            yield client
        finally:
            # Limpiar la base de datos de prueba
            if client.db:
                await client.db.client.drop_database("binance_test")
            await client.close()

    async def test_connection(self, db_client):
        """
        Prueba que la conexión a MongoDB funciona correctamente.
        """
        assert db_client.client is not None
        assert db_client.db is not None

    async def test_get_collection_name(self, db_client):
        """
        Prueba que el nombre de colección se genera correctamente.
        """
        assert db_client._get_collection_name("BTCUSDT") == "klines_btcusdt"
        assert db_client._get_collection_name("btcusdt") == "klines_btcusdt"
        assert db_client._get_collection_name("ETHUSDT") == "klines_ethusdt"

    async def test_get_last_timestamp_empty(self, db_client):
        """
        Prueba obtener el último timestamp cuando no hay datos.
        """
        last_ts = await db_client.get_last_timestamp("BTCUSDT")
        assert last_ts is None

    async def test_insert_and_get_klines(self, db_client):
        """
        Prueba insertar y recuperar klines.
        """
        # Crear datos de prueba
        test_klines = [
            {
                "open_time": 1717200000000,
                "open": 67000.0,
                "high": 67500.0,
                "low": 66500.0,
                "close": 67200.0,
                "volume": 100.5,
                "close_time": 1717200059999,
                "quote_asset_volume": 6720000.0,
                "number_of_trades": 1000,
                "taker_buy_base_asset_volume": 50.0,
                "taker_buy_quote_asset_volume": 3360000.0,
                "timestamp": datetime.fromtimestamp(1717200000000 / 1000, tz=timezone.utc)
            },
            {
                "open_time": 1717200060000,
                "open": 67200.0,
                "high": 67800.0,
                "low": 67100.0,
                "close": 67500.0,
                "volume": 120.3,
                "close_time": 1717200119999,
                "quote_asset_volume": 8100000.0,
                "number_of_trades": 1200,
                "taker_buy_base_asset_volume": 60.0,
                "taker_buy_quote_asset_volume": 4050000.0,
                "timestamp": datetime.fromtimestamp(1717200060000 / 1000, tz=timezone.utc)
            }
        ]

        # Insertar datos
        inserted = await db_client.insert_klines("BTCUSDT", test_klines)
        assert inserted == 2

        # Recuperar datos
        klines = await db_client.get_klines("BTCUSDT")
        assert len(klines) == 2
        assert klines[0]["open_time"] == 1717200000000
        assert klines[1]["open_time"] == 1717200060000

    async def test_insert_duplicate_klines(self, db_client):
        """
        Prueba que los duplicados se manejan correctamente.
        """
        # Crear dato de prueba
        test_kline = {
            "open_time": 1717200000000,
            "open": 67000.0,
            "high": 67500.0,
            "low": 66500.0,
            "close": 67200.0,
            "volume": 100.5,
            "close_time": 1717200059999,
            "quote_asset_volume": 6720000.0,
            "number_of_trades": 1000,
            "taker_buy_base_asset_volume": 50.0,
            "taker_buy_quote_asset_volume": 3360000.0,
            "timestamp": datetime.fromtimestamp(1717200000000 / 1000, tz=timezone.utc)
        }

        # Insertar dos veces
        await db_client.insert_klines("BTCUSDT", [test_kline])
        await db_client.insert_klines("BTCUSDT", [test_kline])

        # Debe haber solo un registro
        klines = await db_client.get_klines("BTCUSDT")
        assert len(klines) == 1

    async def test_get_last_timestamp_with_data(self, db_client):
        """
        Prueba obtener el último timestamp cuando hay datos.
        """
        # Insertar datos de prueba
        test_klines = [
            {
                "open_time": 1717200000000,
                "close_time": 1717200059999,
                "open": 67000.0,
                "high": 67500.0,
                "low": 66500.0,
                "close": 67200.0,
                "volume": 100.5,
                "quote_asset_volume": 6720000.0,
                "number_of_trades": 1000,
                "taker_buy_base_asset_volume": 50.0,
                "taker_buy_quote_asset_volume": 3360000.0,
                "timestamp": datetime.fromtimestamp(1717200000000 / 1000, tz=timezone.utc)
            },
            {
                "open_time": 1717200060000,
                "close_time": 1717200119999,
                "open": 67200.0,
                "high": 67800.0,
                "low": 67100.0,
                "close": 67500.0,
                "volume": 120.3,
                "quote_asset_volume": 8100000.0,
                "number_of_trades": 1200,
                "taker_buy_base_asset_volume": 60.0,
                "taker_buy_quote_asset_volume": 4050000.0,
                "timestamp": datetime.fromtimestamp(1717200060000 / 1000, tz=timezone.utc)
            }
        ]

        await db_client.insert_klines("BTCUSDT", test_klines)

        # Obtener último timestamp
        last_ts = await db_client.get_last_timestamp("BTCUSDT")
        assert last_ts == 1717200119999

    async def test_get_statistics(self, db_client):
        """
        Prueba obtener estadísticas de una colección.
        """
        # Insertar datos de prueba
        test_klines = [
            {
                "open_time": 1717200000000,
                "close_time": 1717200059999,
                "open": 67000.0,
                "high": 67500.0,
                "low": 66500.0,
                "close": 67200.0,
                "volume": 100.5,
                "quote_asset_volume": 6720000.0,
                "number_of_trades": 1000,
                "taker_buy_base_asset_volume": 50.0,
                "taker_buy_quote_asset_volume": 3360000.0,
                "timestamp": datetime.fromtimestamp(1717200000000 / 1000, tz=timezone.utc)
            }
        ]

        await db_client.insert_klines("BTCUSDT", test_klines)

        # Obtener estadísticas
        stats = await db_client.get_statistics("BTCUSDT")

        assert stats["symbol"] == "BTCUSDT"
        assert stats["total_records"] == 1
        assert stats["first_record"] is not None
        assert stats["last_record"] is not None

    async def test_statistics_empty_collection(self, db_client):
        """
        Prueba estadísticas de una colección vacía.
        """
        stats = await db_client.get_statistics("ETHUSDT")

        assert stats["symbol"] == "ETHUSDT"
        assert stats["total_records"] == 0
        assert stats["first_record"] is None
        assert stats["last_record"] is None
