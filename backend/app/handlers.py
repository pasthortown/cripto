"""
Handlers de Tornado para los endpoints REST.
Maneja las solicitudes HTTP y coordina entre Binance API y MongoDB.
"""

import tornado.web
import json
from datetime import datetime, timezone, timedelta
import logging

from binance_client import BinanceClient
from db_client import MongoDBClient
from config import DEFAULT_START_TIMESTAMP, DEFAULT_INTERVAL
from websocket_manager import connection_manager

# Obtener logger
logger = logging.getLogger(__name__)


class BaseHandler(tornado.web.RequestHandler):
    """Handler base con funcionalidades comunes."""

    def set_default_headers(self):
        """Configura headers CORS y content-type."""
        self.set_header("Content-Type", "application/json")
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")

    def options(self, *args):
        """Maneja peticiones OPTIONS para CORS."""
        self.set_status(204)
        self.finish()

    def write_error(self, status_code, **kwargs):
        """Maneja errores y retorna JSON."""
        error_message = {
            "error": True,
            "status_code": status_code,
            "message": self._reason
        }

        if "exc_info" in kwargs:
            import traceback
            error_message["traceback"] = traceback.format_exception(*kwargs["exc_info"])

        self.write(json.dumps(error_message))


class SyncDataHandler(BaseHandler):
    """
    Handler para sincronizar datos de una moneda desde Binance.

    Endpoint: POST /api/sync
    Body: {"symbol": "BTCUSDT"}

    Funcionalidad:
    1. Valida si hay datos en la BD para esa moneda
    2. Si hay datos, obtiene desde la última fecha hasta ahora
    3. Si no hay datos, obtiene desde el 1-6-2025 hasta ahora
    4. Almacena los datos en MongoDB
    """

    async def post(self):
        """
        Sincroniza datos de una moneda específica.

        Request body:
        {
            "symbol": "BTCUSDT"
        }
        """
        try:
            # Parsear el body de la petición
            body = json.loads(self.request.body)
            symbol = body.get("symbol", "").upper()

            if not symbol:
                self.set_status(400)
                self.write(json.dumps({
                    "error": True,
                    "message": "El parámetro 'symbol' es requerido"
                }))
                return

            logger.info(f"Iniciando sincronización de {symbol}")

            # Obtener instancia de MongoDB desde la aplicación
            db_client: MongoDBClient = self.application.settings.get("db_client")

            # Verificar si hay datos previos en la base de datos
            last_timestamp = await db_client.get_last_timestamp(symbol)

            # Determinar el timestamp de inicio
            if last_timestamp:
                # Si hay datos, comenzar desde el último registro + 1ms
                start_time = last_timestamp + 1
                logger.info(f"Sincronización incremental desde {datetime.fromtimestamp(start_time/1000)}")
            else:
                # Si no hay datos, comenzar desde la fecha por defecto (1-6-2025)
                start_time = DEFAULT_START_TIMESTAMP
                logger.info(f"Primera sincronización desde {datetime.fromtimestamp(start_time/1000)}")

            # Timestamp del ÚLTIMO MINUTO COMPLETO (no el actual que está en progreso)
            # Si ahora son las 19:38:45, solo pedimos hasta 19:37:59.999
            now = datetime.now(timezone.utc)
            # Minuto actual (sin segundos)
            current_minute = now.replace(second=0, microsecond=0)
            # Minuto anterior (último completo)
            last_complete_minute = current_minute - timedelta(minutes=1)
            # Fin del minuto anterior: 23:59:59.999
            end_time = int((last_complete_minute.replace(second=59, microsecond=999999)).timestamp() * 1000)

            logger.info(f"Obteniendo datos hasta el último minuto completo: {datetime.fromtimestamp(end_time/1000)}")

            # Obtener datos de Binance
            async with BinanceClient() as binance_client:
                klines = await binance_client.get_all_klines_in_range(
                    symbol=symbol,
                    start_time=start_time,
                    end_time=end_time,
                    interval=DEFAULT_INTERVAL
                )

            # Guardar en MongoDB
            inserted_count = await db_client.insert_klines(symbol, klines)

            # Obtener estadísticas
            stats = await db_client.get_statistics(symbol)

            # Notificar a clientes WebSocket sobre los nuevos datos
            if inserted_count > 0:
                # Obtener el último precio si hay datos
                last_price = klines[-1].get("close", 0) if klines else 0

                connection_manager.notify_sync_complete(symbol, {
                    "new_records": inserted_count,
                    "total_records": stats.get("total_records", 0),
                    "last_price": last_price,
                    "last_record": stats.get("last_record")
                })
                logger.info(f"Notificación WebSocket enviada para {symbol}")

            # Respuesta exitosa
            self.write(json.dumps({
                "success": True,
                "symbol": symbol,
                "new_records": inserted_count,
                "statistics": stats
            }))

        except json.JSONDecodeError:
            self.set_status(400)
            self.write(json.dumps({
                "error": True,
                "message": "JSON inválido en el body"
            }))
        except Exception as e:
            logger.error(f"Error en sincronización: {e}", exc_info=True)
            self.set_status(500)
            self.write(json.dumps({
                "error": True,
                "message": str(e)
            }))


class GetDataHandler(BaseHandler):
    """
    Handler para obtener datos almacenados de una moneda.

    Endpoint: GET /api/data/{symbol}?start_time={timestamp}&end_time={timestamp}&limit={limit}

    Retorna los datos almacenados en MongoDB para una moneda específica.
    """

    async def get(self, symbol: str):
        """
        Obtiene datos de una moneda desde MongoDB.

        Args:
            symbol: Par de trading (BTCUSDT, ETHUSDT, etc.)

        Query params (opcionales):
            start_time: Timestamp en milisegundos
            end_time: Timestamp en milisegundos
            limit: Cantidad máxima de registros
        """
        try:
            symbol = symbol.upper()

            # Obtener parámetros de query
            start_time = self.get_argument("start_time", None)
            end_time = self.get_argument("end_time", None)
            limit = self.get_argument("limit", None)

            # Convertir a int si existen
            if start_time:
                start_time = int(start_time)
            if end_time:
                end_time = int(end_time)
            if limit:
                limit = int(limit)

            logger.info(f"Solicitando datos de {symbol}")

            # Obtener instancia de MongoDB
            db_client: MongoDBClient = self.application.settings.get("db_client")

            # Obtener datos
            klines = await db_client.get_klines(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )

            # Respuesta exitosa
            self.write(json.dumps({
                "success": True,
                "symbol": symbol,
                "count": len(klines),
                "data": klines
            }, default=str))  # default=str para serializar datetime

        except ValueError:
            self.set_status(400)
            self.write(json.dumps({
                "error": True,
                "message": "Parámetros inválidos. start_time, end_time y limit deben ser números"
            }))
        except Exception as e:
            logger.error(f"Error al obtener datos: {e}", exc_info=True)
            self.set_status(500)
            self.write(json.dumps({
                "error": True,
                "message": str(e)
            }))


class StatsHandler(BaseHandler):
    """
    Handler para obtener estadísticas de una moneda.

    Endpoint: GET /api/stats/{symbol}

    Retorna estadísticas sobre los datos almacenados.
    """

    async def get(self, symbol: str):
        """
        Obtiene estadísticas de una moneda.

        Args:
            symbol: Par de trading (BTCUSDT, ETHUSDT, etc.)
        """
        try:
            symbol = symbol.upper()
            logger.info(f"Solicitando estadísticas de {symbol}")

            # Obtener instancia de MongoDB
            db_client: MongoDBClient = self.application.settings.get("db_client")

            # Obtener estadísticas
            stats = await db_client.get_statistics(symbol)

            # Respuesta exitosa
            self.write(json.dumps({
                "success": True,
                "statistics": stats
            }))

        except Exception as e:
            logger.error(f"Error al obtener estadísticas: {e}", exc_info=True)
            self.set_status(500)
            self.write(json.dumps({
                "error": True,
                "message": str(e)
            }))


class SymbolsHandler(BaseHandler):
    """
    Handler para obtener la lista de monedas disponibles.

    Endpoint: GET /api/symbols

    Retorna todas las monedas que tienen datos almacenados en la base de datos.
    """

    async def get(self):
        """
        Obtiene la lista de todos los símbolos disponibles en la base de datos.
        Útil para que el frontend pueda mostrar qué monedas están disponibles.
        """
        try:
            logger.info("Solicitando lista de símbolos disponibles")

            # Obtener instancia de MongoDB
            db_client: MongoDBClient = self.application.settings.get("db_client")

            # Obtener símbolos disponibles
            symbols = await db_client.get_available_symbols()

            # Respuesta exitosa
            self.write(json.dumps({
                "success": True,
                "count": len(symbols),
                "symbols": symbols
            }))

        except Exception as e:
            logger.error(f"Error al obtener símbolos: {e}", exc_info=True)
            self.set_status(500)
            self.write(json.dumps({
                "error": True,
                "message": str(e)
            }))


class PredictionsHandler(BaseHandler):
    """
    Handler para obtener predicciones de una moneda.

    Endpoint: GET /api/predictions/{symbol}?start_time={timestamp}&end_time={timestamp}&limit={limit}

    Retorna las predicciones almacenadas en MongoDB para una moneda específica.
    """

    async def get(self, symbol: str):
        """
        Obtiene predicciones de una moneda desde MongoDB.

        Args:
            symbol: Par de trading (BTCUSDT, ETHUSDT, etc.)

        Query params (opcionales):
            start_time: Timestamp en milisegundos
            end_time: Timestamp en milisegundos
            limit: Cantidad máxima de registros
        """
        try:
            symbol = symbol.upper()

            # Obtener parámetros de query
            start_time = self.get_argument("start_time", None)
            end_time = self.get_argument("end_time", None)
            limit = self.get_argument("limit", None)

            # Convertir a int si existen
            if start_time:
                start_time = int(start_time)
            if end_time:
                end_time = int(end_time)
            if limit:
                limit = int(limit)

            logger.info(f"Solicitando predicciones de {symbol}")

            # Obtener instancia de MongoDB
            db_client: MongoDBClient = self.application.settings.get("db_client")

            # Obtener predicciones
            predictions = await db_client.get_predictions(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )

            # Respuesta exitosa
            self.write(json.dumps({
                "success": True,
                "symbol": symbol,
                "count": len(predictions),
                "data": predictions
            }, default=str))  # default=str para serializar datetime

        except ValueError:
            self.set_status(400)
            self.write(json.dumps({
                "error": True,
                "message": "Parámetros inválidos. start_time, end_time y limit deben ser números"
            }))
        except Exception as e:
            logger.error(f"Error al obtener predicciones: {e}", exc_info=True)
            self.set_status(500)
            self.write(json.dumps({
                "error": True,
                "message": str(e)
            }))


class HealthHandler(BaseHandler):
    """
    Handler para verificar el estado del servicio.

    Endpoint: GET /health
    """

    async def get(self):
        """Verifica que el servicio esté funcionando correctamente."""
        try:
            # Verificar conexión a MongoDB
            db_client: MongoDBClient = self.application.settings.get("db_client")
            await db_client.client.admin.command('ping')

            self.write(json.dumps({
                "status": "healthy",
                "service": "binance-backend",
                "database": "connected"
            }))

        except Exception as e:
            self.set_status(503)
            self.write(json.dumps({
                "status": "unhealthy",
                "service": "binance-backend",
                "database": "disconnected",
                "error": str(e)
            }))
