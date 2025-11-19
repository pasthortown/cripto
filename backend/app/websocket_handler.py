"""
WebSocket handler para Tornado.
Maneja conexiones WebSocket para notificaciones en tiempo real.
"""

import tornado.websocket
import json
import logging
from websocket_manager import connection_manager

# Obtener logger
logger = logging.getLogger(__name__)


class UpdatesWebSocketHandler(tornado.websocket.WebSocketHandler):
    """
    WebSocket handler para actualizaciones en tiempo real.

    Endpoint: ws://backend:8888/ws/updates

    Mensajes que puede recibir del cliente:
    1. Suscribirse a símbolos:
       {"action": "subscribe", "symbols": ["BTCUSDT", "ETHUSDT"]}

    2. Desuscribirse de símbolos:
       {"action": "unsubscribe", "symbols": ["BTCUSDT"]}

    3. Ping/Pong (heartbeat):
       {"action": "ping"}

    4. Obtener estadísticas de conexiones:
       {"action": "stats"}

    Mensajes que envía al cliente:
    1. Nuevos datos disponibles:
       {
         "type": "new_data",
         "symbol": "BTCUSDT",
         "timestamp": "2025-11-13T23:45:00",
         "data": {
           "new_records": 1,
           "total_records": 239024,
           "last_price": 100373.48
         }
       }

    2. Sincronización completada:
       {
         "type": "sync_complete",
         "symbol": "BTCUSDT",
         "timestamp": "2025-11-13T23:45:00",
         "statistics": {...}
       }

    3. Confirmación de suscripción:
       {
         "type": "subscribed",
         "symbols": ["BTCUSDT", "ETHUSDT"]
       }

    4. Pong (respuesta a ping):
       {
         "type": "pong",
         "timestamp": "2025-11-13T23:45:00"
       }
    """

    def check_origin(self, origin):
        """
        Permite conexiones desde cualquier origen (CORS).
        En producción, deberías restringir esto a dominios específicos.

        Args:
            origin: Origen de la conexión

        Returns:
            True para permitir la conexión
        """
        # En producción, verificar el origen:
        # allowed_origins = ["http://localhost:3000", "https://tu-dominio.com"]
        # return origin in allowed_origins
        return True

    def open(self):
        """
        Se ejecuta cuando se abre una nueva conexión WebSocket.
        """
        # Agregar esta conexión al manager
        connection_manager.add_connection(self)

        logger.info(f"Nueva conexión WebSocket abierta desde {self.request.remote_ip}")

        # Enviar mensaje de bienvenida
        self.send_message({
            "type": "connected",
            "message": "Conectado al servidor de actualizaciones de Binance",
            "timestamp": self._get_timestamp()
        })

    def on_close(self):
        """
        Se ejecuta cuando se cierra una conexión WebSocket.
        """
        # Remover esta conexión del manager
        connection_manager.remove_connection(self)

        logger.info(f"Conexión WebSocket cerrada desde {self.request.remote_ip}")

    def on_message(self, message):
        """
        Se ejecuta cuando se recibe un mensaje del cliente.

        Args:
            message: Mensaje recibido (string JSON)
        """
        try:
            # Parsear mensaje JSON
            data = json.loads(message)
            action = data.get("action")

            logger.debug(f"Mensaje recibido: {action}")

            # Procesar según la acción
            if action == "subscribe":
                self._handle_subscribe(data)

            elif action == "unsubscribe":
                self._handle_unsubscribe(data)

            elif action == "ping":
                self._handle_ping()

            elif action == "stats":
                self._handle_stats()

            else:
                self.send_error(f"Acción desconocida: {action}")

        except json.JSONDecodeError:
            self.send_error("Mensaje inválido: no es JSON válido")
            logger.error(f"Mensaje JSON inválido recibido: {message}")

        except Exception as e:
            self.send_error(f"Error al procesar mensaje: {str(e)}")
            logger.error(f"Error al procesar mensaje: {e}", exc_info=True)

    def _handle_subscribe(self, data: dict):
        """
        Maneja la suscripción a símbolos.

        Args:
            data: Datos del mensaje con símbolos a suscribir
        """
        symbols = data.get("symbols", [])

        if not symbols:
            self.send_error("Debe especificar al menos un símbolo")
            return

        # Suscribir a los símbolos
        connection_manager.subscribe(self, symbols)

        # Confirmar suscripción
        self.send_message({
            "type": "subscribed",
            "symbols": [s.upper() for s in symbols],
            "timestamp": self._get_timestamp()
        })

        logger.info(f"Cliente suscrito a: {', '.join(symbols)}")

    def _handle_unsubscribe(self, data: dict):
        """
        Maneja la desuscripción de símbolos.

        Args:
            data: Datos del mensaje con símbolos a desuscribir
        """
        symbols = data.get("symbols", [])

        if not symbols:
            self.send_error("Debe especificar al menos un símbolo")
            return

        # Desuscribir de los símbolos
        connection_manager.unsubscribe(self, symbols)

        # Confirmar desuscripción
        self.send_message({
            "type": "unsubscribed",
            "symbols": [s.upper() for s in symbols],
            "timestamp": self._get_timestamp()
        })

        logger.info(f"Cliente desuscrito de: {', '.join(symbols)}")

    def _handle_ping(self):
        """
        Maneja el mensaje de ping (heartbeat).
        """
        self.send_message({
            "type": "pong",
            "timestamp": self._get_timestamp()
        })

    def _handle_stats(self):
        """
        Envía estadísticas del servidor al cliente.
        """
        stats = connection_manager.get_stats()

        self.send_message({
            "type": "stats",
            "data": stats,
            "timestamp": self._get_timestamp()
        })

    def send_message(self, message: dict):
        """
        Envía un mensaje al cliente.

        Args:
            message: Diccionario con el mensaje a enviar
        """
        try:
            self.write_message(json.dumps(message))
        except Exception as e:
            logger.error(f"Error al enviar mensaje: {e}")

    def send_error(self, error_message: str):
        """
        Envía un mensaje de error al cliente.

        Args:
            error_message: Mensaje de error
        """
        self.send_message({
            "type": "error",
            "message": error_message,
            "timestamp": self._get_timestamp()
        })

    @staticmethod
    def _get_timestamp() -> str:
        """
        Obtiene el timestamp actual en formato ISO.

        Returns:
            Timestamp en formato ISO
        """
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'
