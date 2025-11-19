"""
Aplicación principal del backend de Binance.
Configura el servidor Tornado y los endpoints REST.
"""

import tornado.ioloop
import tornado.web
import logging
import asyncio

from handlers import SyncDataHandler, GetDataHandler, StatsHandler, SymbolsHandler, PredictionsHandler, HealthHandler
from websocket_handler import UpdatesWebSocketHandler
from db_client import MongoDBClient
from logger_config import setup_logging, get_logger
from config import (
    MONGODB_HOST, MONGODB_PORT, MONGODB_DATABASE,
    MONGODB_USERNAME, MONGODB_PASSWORD,
    SERVER_PORT, LOG_LEVEL, LOG_DIR
)

# Configurar logging con archivos .txt y rotación
setup_logging(log_level=LOG_LEVEL, log_dir=LOG_DIR)
logger = get_logger(__name__)


class Application(tornado.web.Application):
    """
    Aplicación Tornado principal.
    Define las rutas y configuraciones del servidor.
    """

    def __init__(self):
        """
        Inicializa la aplicación con sus rutas y configuraciones.
        """

        # Definir rutas del API
        handlers = [
            # Endpoint de salud
            (r"/health", HealthHandler),

            # WebSocket para actualizaciones en tiempo real
            (r"/ws/updates", UpdatesWebSocketHandler),

            # Endpoint para listar monedas disponibles
            (r"/api/symbols", SymbolsHandler),

            # Endpoint para sincronizar datos de una moneda
            (r"/api/sync", SyncDataHandler),

            # Endpoint para obtener datos de una moneda
            (r"/api/data/([A-Z]+)", GetDataHandler),

            # Endpoint para obtener estadísticas de una moneda
            (r"/api/stats/([A-Z]+)", StatsHandler),

            # Endpoint para obtener predicciones de una moneda
            (r"/api/predictions/([A-Z]+)", PredictionsHandler),
        ]

        # Configuraciones de la aplicación
        settings = {
            "debug": False,  # Cambiar a False en producción
            "autoreload": False,
        }

        super().__init__(handlers, **settings)

        # Inicializar cliente de MongoDB (se conectará en startup)
        self.db_client = None

    async def init_database(self):
        """
        Inicializa la conexión con MongoDB.
        """
        try:
            self.db_client = MongoDBClient(
                host=MONGODB_HOST,
                port=MONGODB_PORT,
                database=MONGODB_DATABASE,
                username=MONGODB_USERNAME,
                password=MONGODB_PASSWORD
            )
            await self.db_client.connect()
            # Guardar la instancia en settings para que los handlers puedan acceder
            self.settings["db_client"] = self.db_client
            logger.info("Base de datos inicializada correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar la base de datos: {e}")
            raise

    async def close_database(self):
        """
        Cierra la conexión con MongoDB.
        """
        if self.db_client:
            await self.db_client.close()
            logger.info("Conexión con base de datos cerrada")


async def main():
    """
    Función principal que arranca el servidor.
    """
    try:
        # Crear aplicación
        app = Application()

        # Inicializar base de datos
        await app.init_database()

        # Crear servidor HTTP
        app.listen(SERVER_PORT)
        logger.info(f"🚀 Servidor Tornado iniciado en puerto {SERVER_PORT}")
        logger.info(f"📊 Endpoints disponibles:")
        logger.info(f"   - GET  /health")
        logger.info(f"   - WS   /ws/updates")
        logger.info(f"   - GET  /api/symbols")
        logger.info(f"   - POST /api/sync")
        logger.info(f"   - GET  /api/data/{{symbol}}")
        logger.info(f"   - GET  /api/stats/{{symbol}}")
        logger.info(f"   - GET  /api/predictions/{{symbol}}")

        # Mantener el servidor corriendo
        await asyncio.Event().wait()

    except KeyboardInterrupt:
        logger.info("Deteniendo servidor...")
    except Exception as e:
        logger.error(f"Error al iniciar el servidor: {e}", exc_info=True)
    finally:
        # Cerrar conexión con la base de datos
        await app.close_database()


if __name__ == "__main__":
    """
    Punto de entrada de la aplicación.
    """
    # Ejecutar el servidor
    asyncio.run(main())
