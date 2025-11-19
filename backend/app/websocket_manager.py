"""
Manager para gestionar conexiones WebSocket y broadcast de mensajes.
Maneja suscripciones de clientes a símbolos específicos.
"""

import logging
from typing import Set, Dict, List, Optional
import json
from datetime import datetime

# Obtener logger
logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Gestiona todas las conexiones WebSocket activas y sus suscripciones.
    Permite broadcast de mensajes a clientes específicos o a todos.
    """

    def __init__(self):
        """Inicializa el manager de conexiones."""
        # Todas las conexiones activas
        self.connections: Set = set()

        # Mapa de símbolos a conexiones suscritas
        # {"BTCUSDT": {connection1, connection2}, "ETHUSDT": {connection1}}
        self.subscriptions: Dict[str, Set] = {}

        logger.info("ConnectionManager inicializado")

    def add_connection(self, connection):
        """
        Agrega una nueva conexión WebSocket.

        Args:
            connection: WebSocket connection handler
        """
        self.connections.add(connection)
        logger.info(f"Nueva conexión WebSocket agregada. Total: {len(self.connections)}")

    def remove_connection(self, connection):
        """
        Remueve una conexión WebSocket.

        Args:
            connection: WebSocket connection handler
        """
        # Remover de las conexiones activas
        self.connections.discard(connection)

        # Remover de todas las suscripciones
        for symbol, subscribers in list(self.subscriptions.items()):
            subscribers.discard(connection)
            # Si no quedan suscriptores, eliminar el símbolo
            if not subscribers:
                del self.subscriptions[symbol]

        logger.info(f"Conexión WebSocket removida. Total: {len(self.connections)}")

    def subscribe(self, connection, symbols: List[str]):
        """
        Suscribe una conexión a uno o más símbolos.

        Args:
            connection: WebSocket connection handler
            symbols: Lista de símbolos a los que suscribirse
        """
        for symbol in symbols:
            symbol = symbol.upper()

            if symbol not in self.subscriptions:
                self.subscriptions[symbol] = set()

            self.subscriptions[symbol].add(connection)
            logger.info(f"Conexión suscrita a {symbol}. Suscriptores: {len(self.subscriptions[symbol])}")

    def unsubscribe(self, connection, symbols: List[str]):
        """
        Desuscribe una conexión de uno o más símbolos.

        Args:
            connection: WebSocket connection handler
            symbols: Lista de símbolos de los que desuscribirse
        """
        for symbol in symbols:
            symbol = symbol.upper()

            if symbol in self.subscriptions:
                self.subscriptions[symbol].discard(connection)

                # Si no quedan suscriptores, eliminar el símbolo
                if not self.subscriptions[symbol]:
                    del self.subscriptions[symbol]

                logger.info(f"Conexión desuscrita de {symbol}")

    def get_subscribers(self, symbol: str) -> Set:
        """
        Obtiene todos los suscriptores de un símbolo.

        Args:
            symbol: Símbolo del que obtener suscriptores

        Returns:
            Set de conexiones suscritas al símbolo
        """
        return self.subscriptions.get(symbol.upper(), set())

    def broadcast_to_all(self, message: dict):
        """
        Envía un mensaje a todas las conexiones activas.

        Args:
            message: Diccionario con el mensaje a enviar
        """
        if not self.connections:
            logger.debug("No hay conexiones activas para broadcast")
            return

        message_json = json.dumps(message)
        dead_connections = set()

        for connection in self.connections:
            try:
                connection.write_message(message_json)
            except Exception as e:
                logger.error(f"Error al enviar mensaje a conexión: {e}")
                dead_connections.add(connection)

        # Limpiar conexiones muertas
        for connection in dead_connections:
            self.remove_connection(connection)

        logger.info(f"Broadcast enviado a {len(self.connections)} conexiones")

    def broadcast_to_symbol(self, symbol: str, message: dict):
        """
        Envía un mensaje a todos los suscriptores de un símbolo específico.

        Args:
            symbol: Símbolo a cuyos suscriptores enviar el mensaje
            message: Diccionario con el mensaje a enviar
        """
        subscribers = self.get_subscribers(symbol)

        if not subscribers:
            logger.debug(f"No hay suscriptores para {symbol}")
            return

        message_json = json.dumps(message)
        dead_connections = set()

        for connection in subscribers:
            try:
                connection.write_message(message_json)
            except Exception as e:
                logger.error(f"Error al enviar mensaje a suscriptor de {symbol}: {e}")
                dead_connections.add(connection)

        # Limpiar conexiones muertas
        for connection in dead_connections:
            self.remove_connection(connection)

        logger.info(f"Mensaje enviado a {len(subscribers)} suscriptores de {symbol}")

    def notify_new_data(self, symbol: str, data: dict):
        """
        Notifica a los suscriptores que hay nuevos datos disponibles para un símbolo.

        Args:
            symbol: Símbolo con nuevos datos
            data: Información sobre los nuevos datos
        """
        message = {
            "type": "new_data",
            "symbol": symbol.upper(),
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }

        self.broadcast_to_symbol(symbol, message)
        logger.info(f"Notificación de nuevos datos enviada para {symbol}")

    def notify_sync_complete(self, symbol: str, stats: dict):
        """
        Notifica que se completó una sincronización para un símbolo.

        Args:
            symbol: Símbolo sincronizado
            stats: Estadísticas de la sincronización
        """
        message = {
            "type": "sync_complete",
            "symbol": symbol.upper(),
            "timestamp": datetime.utcnow().isoformat(),
            "statistics": stats
        }

        self.broadcast_to_symbol(symbol, message)
        logger.info(f"Notificación de sincronización completada para {symbol}")

    def get_stats(self) -> dict:
        """
        Obtiene estadísticas del manager de conexiones.

        Returns:
            Diccionario con estadísticas
        """
        return {
            "total_connections": len(self.connections),
            "subscriptions": {
                symbol: len(subscribers)
                for symbol, subscribers in self.subscriptions.items()
            }
        }


# Instancia global del ConnectionManager
connection_manager = ConnectionManager()
