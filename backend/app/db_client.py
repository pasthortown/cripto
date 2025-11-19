"""
Cliente para interactuar con MongoDB.
Maneja el almacenamiento y recuperación de datos de criptomonedas.
Cada moneda se almacena en una colección separada.
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Dict, Optional
from datetime import datetime, timezone
import logging

# Obtener logger
logger = logging.getLogger(__name__)


class MongoDBClient:
    """
    Cliente asíncrono para interactuar con MongoDB.
    Utiliza Motor, el driver asíncrono oficial de MongoDB para Python.
    """

    def __init__(
        self,
        host: str = "mongodb",
        port: int = 27017,
        database: str = "binance_data",
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Inicializa el cliente de MongoDB.

        Args:
            host: Host de MongoDB (nombre del servicio en Docker)
            port: Puerto de MongoDB (27017 dentro del contenedor)
            database: Nombre de la base de datos
            username: Usuario de MongoDB (opcional)
            password: Contraseña de MongoDB (opcional)
        """
        # Construir connection string con o sin autenticación
        if username and password:
            self.connection_string = f"mongodb://{username}:{password}@{host}:{port}/?authSource=admin"
        else:
            self.connection_string = f"mongodb://{host}:{port}"

        self.database_name = database
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None

    async def connect(self):
        """Establece la conexión con MongoDB."""
        try:
            self.client = AsyncIOMotorClient(self.connection_string)
            self.db = self.client[self.database_name]
            # Verificar conexión
            await self.client.admin.command('ping')
            logger.info(f"Conectado exitosamente a MongoDB en {self.connection_string}")
        except Exception as e:
            logger.error(f"Error al conectar con MongoDB: {e}")
            raise

    async def close(self):
        """Cierra la conexión con MongoDB."""
        if self.client:
            self.client.close()
            logger.info("Conexión con MongoDB cerrada")

    def _get_collection_name(self, symbol: str) -> str:
        """
        Genera el nombre de la colección para un símbolo específico.
        Cada moneda tiene su propia colección.

        Args:
            symbol: Par de trading (ej: BTCUSDT)

        Returns:
            Nombre de la colección (ej: klines_btcusdt)
        """
        return f"klines_{symbol.lower()}"

    async def get_last_timestamp(self, symbol: str) -> Optional[int]:
        """
        Obtiene el timestamp del último registro almacenado para un símbolo.
        Esto permite hacer sincronización incremental.

        Args:
            symbol: Par de trading (ej: BTCUSDT)

        Returns:
            Timestamp en milisegundos del último registro, o None si no hay datos
        """
        collection_name = self._get_collection_name(symbol)
        collection = self.db[collection_name]

        try:
            # Buscar el documento con el timestamp más reciente
            last_doc = await collection.find_one(
                sort=[("close_time", -1)]
            )

            if last_doc:
                logger.info(f"Último registro de {symbol}: {datetime.fromtimestamp(last_doc['close_time']/1000)}")
                return last_doc["close_time"]
            else:
                logger.info(f"No hay datos previos de {symbol} en la base de datos")
                return None

        except Exception as e:
            logger.error(f"Error al obtener último timestamp de {symbol}: {e}")
            raise

    async def insert_klines(self, symbol: str, klines: List[Dict]) -> int:
        """
        Inserta múltiples klines en la colección correspondiente.
        Evita duplicados usando el campo open_time como clave única.

        Args:
            symbol: Par de trading (ej: BTCUSDT)
            klines: Lista de klines a insertar

        Returns:
            Número de documentos insertados
        """
        if not klines:
            logger.info(f"No hay datos para insertar en {symbol}")
            return 0

        collection_name = self._get_collection_name(symbol)
        collection = self.db[collection_name]

        try:
            # Crear índice único en open_time si no existe
            await collection.create_index("open_time", unique=True)
            await collection.create_index("close_time")
            await collection.create_index("timestamp")

            # Insertar documentos, ignorando duplicados
            inserted_count = 0
            for kline in klines:
                try:
                    await collection.update_one(
                        {"open_time": kline["open_time"]},
                        {"$set": kline},
                        upsert=True
                    )
                    inserted_count += 1
                except Exception as e:
                    # Si hay duplicados, continuar con el siguiente
                    logger.debug(f"Documento duplicado ignorado: {e}")
                    continue

            logger.info(f"Insertados/actualizados {inserted_count} registros en {collection_name}")
            return inserted_count

        except Exception as e:
            logger.error(f"Error al insertar klines en {symbol}: {e}")
            raise

    async def get_klines(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Obtiene klines almacenados de la base de datos.

        Args:
            symbol: Par de trading (ej: BTCUSDT)
            start_time: Timestamp en milisegundos desde cuando buscar
            end_time: Timestamp en milisegundos hasta cuando buscar
            limit: Cantidad máxima de registros a retornar

        Returns:
            Lista de klines
        """
        collection_name = self._get_collection_name(symbol)
        collection = self.db[collection_name]

        try:
            # Construir filtro de consulta
            query = {}
            if start_time:
                query["open_time"] = {"$gte": start_time}
            if end_time:
                if "open_time" in query:
                    query["open_time"]["$lte"] = end_time
                else:
                    query["open_time"] = {"$lte": end_time}

            # Ejecutar consulta
            # Si solo se especifica límite sin fechas, queremos los ÚLTIMOS registros
            # Por lo tanto ordenamos DESC, aplicamos límite y luego revertimos
            if limit and not start_time and not end_time:
                # Obtener los últimos N registros (más recientes)
                cursor = collection.find(query).sort("open_time", -1).limit(limit)
                klines = await cursor.to_list(length=None)
                # Revertir para que queden en orden cronológico (ASC)
                klines.reverse()
            else:
                # Comportamiento normal: orden ascendente
                cursor = collection.find(query).sort("open_time", 1)
                if limit:
                    cursor = cursor.limit(limit)
                klines = await cursor.to_list(length=None)

            # Remover el campo _id de MongoDB para serialización JSON
            for kline in klines:
                kline.pop("_id", None)

            logger.info(f"Recuperados {len(klines)} registros de {collection_name}")
            return klines

        except Exception as e:
            logger.error(f"Error al obtener klines de {symbol}: {e}")
            raise

    async def get_statistics(self, symbol: str) -> Dict:
        """
        Obtiene estadísticas de los datos almacenados para un símbolo.

        Args:
            symbol: Par de trading (ej: BTCUSDT)

        Returns:
            Diccionario con estadísticas
        """
        collection_name = self._get_collection_name(symbol)
        collection = self.db[collection_name]

        try:
            total_docs = await collection.count_documents({})

            if total_docs == 0:
                return {
                    "symbol": symbol,
                    "total_records": 0,
                    "first_record": None,
                    "last_record": None
                }

            first_doc = await collection.find_one(sort=[("open_time", 1)])
            last_doc = await collection.find_one(sort=[("open_time", -1)])

            return {
                "symbol": symbol,
                "total_records": total_docs,
                "first_record": datetime.fromtimestamp(first_doc["open_time"] / 1000, tz=timezone.utc).isoformat(),
                "last_record": datetime.fromtimestamp(last_doc["open_time"] / 1000, tz=timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Error al obtener estadísticas de {symbol}: {e}")
            raise

    async def get_available_symbols(self) -> List[Dict]:
        """
        Obtiene la lista de todos los símbolos que tienen datos en la base de datos.
        Útil para que el frontend sepa qué monedas están disponibles.

        Returns:
            Lista de diccionarios con información de cada símbolo disponible
        """
        try:
            # Obtener todas las colecciones de la base de datos
            collection_names = await self.db.list_collection_names()

            # Filtrar solo las colecciones de klines
            symbols_data = []

            for collection_name in collection_names:
                # Solo procesar colecciones que empiecen con "klines_"
                if collection_name.startswith("klines_"):
                    # Extraer el símbolo del nombre de la colección
                    symbol = collection_name.replace("klines_", "").upper()

                    # Obtener estadísticas básicas de la colección
                    collection = self.db[collection_name]
                    total_docs = await collection.count_documents({})

                    if total_docs > 0:
                        # Obtener primer y último registro
                        first_doc = await collection.find_one(sort=[("open_time", 1)])
                        last_doc = await collection.find_one(sort=[("open_time", -1)])

                        symbols_data.append({
                            "symbol": symbol,
                            "total_records": total_docs,
                            "first_record": datetime.fromtimestamp(first_doc["open_time"] / 1000, tz=timezone.utc).isoformat(),
                            "last_record": datetime.fromtimestamp(last_doc["open_time"] / 1000, tz=timezone.utc).isoformat(),
                            "last_price": last_doc.get("close", 0)
                        })

            # Ordenar por símbolo
            symbols_data.sort(key=lambda x: x["symbol"])

            logger.info(f"Se encontraron {len(symbols_data)} símbolos con datos")
            return symbols_data

        except Exception as e:
            logger.error(f"Error al obtener símbolos disponibles: {e}")
            raise

    async def get_predictions(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Obtiene predicciones almacenadas de la base de datos.

        Args:
            symbol: Par de trading (ej: BTCUSDT)
            start_time: Timestamp en milisegundos desde cuando buscar
            end_time: Timestamp en milisegundos hasta cuando buscar
            limit: Cantidad máxima de registros a retornar

        Returns:
            Lista de predicciones
        """
        collection_name = f"prediccion_klines_{symbol.lower()}"
        collection = self.db[collection_name]

        try:
            # Construir filtro de consulta
            query = {}
            if start_time:
                query["open_time"] = {"$gte": start_time}
            if end_time:
                if "open_time" in query:
                    query["open_time"]["$lte"] = end_time
                else:
                    query["open_time"] = {"$lte": end_time}

            # Ejecutar consulta
            cursor = collection.find(query).sort("open_time", 1)

            if limit:
                cursor = cursor.limit(limit)

            predictions = await cursor.to_list(length=None)

            # Remover el campo _id de MongoDB para serialización JSON
            for prediction in predictions:
                prediction.pop("_id", None)

            logger.info(f"Recuperadas {len(predictions)} predicciones de {collection_name}")
            return predictions

        except Exception as e:
            logger.error(f"Error al obtener predicciones de {symbol}: {e}")
            raise
