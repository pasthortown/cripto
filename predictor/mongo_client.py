"""
Cliente para interactuar con MongoDB - Optimizado para datos horarios.
"""

from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pytz
import pandas as pd
from logger_config import setup_logger
import config

logger = setup_logger(__name__, config.LOG_DIR, config.LOG_LEVEL)


class MongoDBClient:
    """Cliente para gestionar operaciones con MongoDB."""

    def __init__(self):
        """Inicializa el cliente de MongoDB."""
        self.client = None
        self.db = None
        self._connect()

    def _connect(self):
        """Establece la conexión con MongoDB."""
        try:
            connection_string = (
                f"mongodb://{config.MONGODB_USERNAME}:{config.MONGODB_PASSWORD}"
                f"@{config.MONGODB_HOST}:{config.MONGODB_PORT}/"
            )
            self.client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=5000
            )
            # Verificar conexión
            self.client.admin.command('ping')
            self.db = self.client[config.MONGODB_DATABASE]
            logger.info(f"Conectado a MongoDB en {config.MONGODB_HOST}:{config.MONGODB_PORT}")
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(f"Error al conectar con MongoDB: {e}")
            raise

    def get_available_symbols(self) -> List[str]:
        """
        Obtiene la lista de símbolos disponibles en la base de datos.

        Returns:
            Lista de símbolos disponibles (sin prefijo 'klines_')
        """
        try:
            # Obtener todas las colecciones
            collections = self.db.list_collection_names()
            # Filtrar solo las colecciones de klines (sin predicciones)
            klines_collections = [
                col for col in collections
                if col.startswith("klines_") and not col.startswith("prediccion_")
            ]
            # Remover el prefijo 'klines_' para obtener solo el símbolo
            symbols = [col.replace("klines_", "") for col in klines_collections]
            logger.info(f"Símbolos disponibles: {symbols}")
            return symbols
        except Exception as e:
            logger.error(f"Error al obtener símbolos disponibles: {e}")
            return []

    def _aggregate_to_hourly(self, minute_data: List[Dict]) -> List[Dict]:
        """
        Agrega datos de minutos a horas.

        Args:
            minute_data: Lista de documentos con datos por minuto

        Returns:
            Lista de documentos con datos por hora
        """
        if not minute_data:
            return []

        # Convertir a DataFrame
        df = pd.DataFrame(minute_data)

        # Convertir timestamp a datetime
        df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
        df['hour'] = df['datetime'].dt.floor('H')

        # Convertir columnas a numérico
        df['open'] = pd.to_numeric(df['open'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])

        # Agrupar por hora
        hourly = df.groupby('hour').agg({
            'open': 'first',     # Primer valor de la hora
            'high': 'max',       # Máximo de la hora
            'low': 'min',        # Mínimo de la hora
            'close': 'last',     # Último valor de la hora
            'volume': 'sum'      # Suma del volumen
        }).reset_index()

        # Convertir de vuelta a formato de documento
        hourly_data = []
        for _, row in hourly.iterrows():
            open_time_ms = int(row['hour'].timestamp() * 1000)
            close_time_ms = open_time_ms + (60 * 60 * 1000) - 1

            doc = {
                'open_time': open_time_ms,
                'open': str(row['open']),
                'high': str(row['high']),
                'low': str(row['low']),
                'close': str(row['close']),
                'volume': str(row['volume']),
                'close_time': close_time_ms
            }
            hourly_data.append(doc)

        return hourly_data

    def get_historical_data(self, symbol: str, minutes: int = 2880, end_time: Optional[datetime] = None) -> List[Dict]:
        """
        Obtiene datos históricos por minuto.

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)
            minutes: Número de minutos de historia a obtener (default: 2880 = 48 horas)
            end_time: Tiempo final hasta el cual obtener datos (default: ahora).
                     Para entrenamiento, usar medianoche del día anterior.

        Returns:
            Lista de documentos con datos históricos por minuto
        """
        try:
            # Agregar prefijo 'klines_' si no está presente
            collection_name = f"klines_{symbol}" if not symbol.startswith('klines_') else symbol
            collection = self.db[collection_name]

            # Usar end_time o ahora
            if end_time is None:
                end_time = datetime.now(pytz.UTC)
            elif end_time.tzinfo is None:
                # Asegurar que end_time tiene zona horaria
                end_time = pytz.UTC.localize(end_time)

            # IMPORTANTE: Truncar end_time al inicio del minuto (eliminar segundos y microsegundos)
            # Esto asegura que buscamos minutos completos y evita problemas de desplazamiento
            end_time = end_time.replace(second=0, microsecond=0)

            # Calcular timestamp de inicio (también truncado al minuto)
            start_time = end_time - timedelta(minutes=minutes)
            start_time = start_time.replace(second=0, microsecond=0)

            start_timestamp = int(start_time.timestamp() * 1000)
            end_timestamp = int(end_time.timestamp() * 1000)

            # Obtener datos de minutos en el rango especificado
            query = {
                "open_time": {
                    "$gte": start_timestamp,
                    "$lte": end_timestamp
                }
            }
            minute_data = list(collection.find(query).sort("open_time", ASCENDING))

            # Si no hay suficientes datos reales, complementar con predicciones
            if len(minute_data) < minutes:
                logger.warning(f"Solo hay {len(minute_data)} datos reales, complementando con predicciones...")

                # Buscar predicciones para completar los datos faltantes
                prediction_collection_name = f"prediccion_klines_{symbol}"
                prediction_collection = self.db[prediction_collection_name]

                # Obtener el último timestamp de los datos reales
                last_real_timestamp = minute_data[-1]['open_time'] if minute_data else start_timestamp

                # Buscar predicciones desde el último dato real hasta end_time
                prediction_query = {
                    "open_time": {
                        "$gt": last_real_timestamp,
                        "$lte": end_timestamp
                    }
                }
                predictions = list(prediction_collection.find(prediction_query).sort("open_time", ASCENDING))

                if predictions:
                    logger.info(f"Agregando {len(predictions)} predicciones a los datos históricos")
                    minute_data.extend(predictions)

            if not minute_data:
                logger.warning(f"No hay datos para {collection_name} desde {start_time} hasta {end_time}")
                return []

            logger.info(f"Datos históricos obtenidos para {collection_name}: {len(minute_data)} minutos (hasta {end_time})")
            return minute_data

        except Exception as e:
            logger.error(f"Error al obtener datos históricos para {symbol}: {e}")
            return []

    def get_all_historical_data(self, symbol: str, end_time: Optional[datetime] = None) -> List[Dict]:
        """
        Obtiene TODOS los datos históricos disponibles hasta una fecha específica.

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)
            end_time: Tiempo final hasta el cual obtener datos (default: ahora).
                     Para entrenamiento, usar medianoche del día anterior.

        Returns:
            Lista de documentos con datos históricos por minuto
        """
        try:
            # Agregar prefijo 'klines_' si no está presente
            collection_name = f"klines_{symbol}" if not symbol.startswith('klines_') else symbol
            collection = self.db[collection_name]

            # Usar end_time o ahora
            if end_time is None:
                end_time = datetime.now(pytz.UTC)
            elif end_time.tzinfo is None:
                # Asegurar que end_time tiene zona horaria
                end_time = pytz.UTC.localize(end_time)

            end_timestamp = int(end_time.timestamp() * 1000)

            # Obtener TODOS los datos hasta end_time
            query = {
                "open_time": {
                    "$lte": end_timestamp
                }
            }
            all_data = list(collection.find(query).sort("open_time", ASCENDING))

            if not all_data:
                logger.warning(f"No hay datos para {collection_name} hasta {end_time}")
                return []

            logger.info(f"TODOS los datos históricos obtenidos para {collection_name}: {len(all_data)} minutos (hasta {end_time})")
            return all_data

        except Exception as e:
            logger.error(f"Error al obtener todos los datos históricos para {symbol}: {e}")
            return []

    def get_kline_by_open_time(self, symbol: str, open_time_ms: int) -> Optional[Dict]:
        """
        Obtiene un dato específico por su open_time.

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)
            open_time_ms: Timestamp del open_time en milisegundos

        Returns:
            Documento con el dato si existe, None si no existe
        """
        try:
            # Agregar prefijo 'klines_' si no está presente
            collection_name = f"klines_{symbol}" if not symbol.startswith('klines_') else symbol
            collection = self.db[collection_name]

            # Buscar por open_time exacto
            query = {"open_time": open_time_ms}
            data = collection.find_one(query)

            return data

        except Exception as e:
            logger.error(f"Error al obtener kline por open_time para {symbol}: {e}")
            return None

    def get_training_data(self, symbol: str, minutes: int = 2880) -> List[Dict]:
        """
        Obtiene datos para entrenamiento (últimos N minutos).

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)
            minutes: Número de minutos de historia (default: 2880 = 48 horas)

        Returns:
            Lista de documentos con datos históricos
        """
        return self.get_historical_data(symbol, minutes)

    def get_validation_data(self, symbol: str, validation_hours: int = 24) -> List[Dict]:
        """
        Obtiene datos recientes para validación.

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)
            validation_hours: Horas de datos para validación (default: 24)

        Returns:
            Lista de documentos con datos de validación
        """
        try:
            # Agregar prefijo 'klines_' si no está presente
            collection_name = f"klines_{symbol}" if not symbol.startswith('klines_') else symbol
            collection = self.db[collection_name]

            # Obtener últimas N horas
            now = datetime.now(pytz.UTC)
            start_time = now - timedelta(hours=validation_hours)
            start_timestamp = int(start_time.timestamp() * 1000)

            query = {"open_time": {"$gte": start_timestamp}}
            minute_data = list(collection.find(query).sort("open_time", ASCENDING))

            if not minute_data:
                logger.warning(f"No hay datos de validación para {collection_name}")
                return []

            # Agregar a datos horarios
            hourly_data = self._aggregate_to_hourly(minute_data)

            logger.info(f"Datos de validación obtenidos para {collection_name}: {len(hourly_data)} horas")
            return hourly_data

        except Exception as e:
            logger.error(f"Error al obtener datos de validación para {symbol}: {e}")
            return []

    def save_predictions(self, symbol: str, predictions: List[Dict]) -> bool:
        """
        Guarda las predicciones en la colección correspondiente.

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)
            predictions: Lista de predicciones a guardar

        Returns:
            True si se guardaron correctamente, False en caso contrario
        """
        try:
            collection_name = f"prediccion_klines_{symbol}"
            collection = self.db[collection_name]

            if predictions:
                # Eliminar predicciones anteriores para las mismas horas (actualizar)
                for pred in predictions:
                    collection.delete_many({'open_time': pred['open_time']})

                # Insertar nuevas predicciones
                collection.insert_many(predictions)
                logger.info(f"Predicciones guardadas para {symbol}: {len(predictions)} minutos")
                return True
            else:
                logger.warning(f"No hay predicciones para guardar para {symbol}")
                return False
        except Exception as e:
            logger.error(f"Error al guardar predicciones para {symbol}: {e}")
            return False

    def check_recent_predictions(self, symbol: str, hours_old: int = 2) -> bool:
        """
        Verifica si existen predicciones recientes (menos de N horas).

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)
            hours_old: Antigüedad máxima de predicciones en horas (default: 2)

        Returns:
            True si existen predicciones recientes, False en caso contrario
        """
        try:
            collection_name = f"prediccion_klines_{symbol}"
            collection = self.db[collection_name]

            # Buscar predicciones creadas en las últimas N horas
            cutoff_time = datetime.now(pytz.UTC) - timedelta(hours=hours_old)

            # Buscar por predicted_at
            query = {
                "predicted_at": {
                    "$gte": cutoff_time.isoformat()
                }
            }

            count = collection.count_documents(query)
            exists = count > 0

            logger.info(f"Predicciones recientes para {symbol}: {'Sí' if exists else 'No'} ({count} registros)")
            return exists

        except Exception as e:
            logger.error(f"Error al verificar predicciones para {symbol}: {e}")
            return False

    def check_predictions_for_today(self, symbol: str) -> bool:
        """
        Verifica si ya existen predicciones para el día actual.

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)

        Returns:
            True si existen predicciones para hoy, False en caso contrario
        """
        try:
            collection_name = f"prediccion_klines_{symbol}"
            collection = self.db[collection_name]

            # Calcular inicio y fin del día actual en UTC
            now = datetime.now(pytz.UTC)
            start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_today = now.replace(hour=23, minute=59, second=59, microsecond=999999)

            start_timestamp = int(start_of_today.timestamp() * 1000)
            end_timestamp = int(end_of_today.timestamp() * 1000)

            # Buscar predicciones con open_time del día actual
            query = {
                "open_time": {
                    "$gte": start_timestamp,
                    "$lte": end_timestamp
                }
            }

            count = collection.count_documents(query)
            exists = count > 0

            logger.info(f"Predicciones para hoy ({start_of_today.date()}) en {symbol}: {'Sí' if exists else 'No'} ({count} registros)")
            return exists

        except Exception as e:
            logger.error(f"Error al verificar predicciones de hoy para {symbol}: {e}")
            return False

    def get_latest_predictions(self, symbol: str, limit: int = 24) -> List[Dict]:
        """
        Obtiene las últimas predicciones para un símbolo.

        Args:
            symbol: Símbolo de la moneda
            limit: Número máximo de predicciones a obtener

        Returns:
            Lista de predicciones ordenadas por tiempo
        """
        try:
            collection_name = f"prediccion_klines_{symbol}"
            collection = self.db[collection_name]

            predictions = list(
                collection.find()
                .sort("open_time", ASCENDING)
                .limit(limit)
            )

            logger.info(f"Últimas predicciones obtenidas para {symbol}: {len(predictions)}")
            return predictions

        except Exception as e:
            logger.error(f"Error al obtener predicciones para {symbol}: {e}")
            return []

    def check_fresh_predictions(self, symbol: str, max_age_hours: int = 1) -> bool:
        """
        Verifica si existen predicciones FRESCAS (generadas recientemente).

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)
            max_age_hours: Edad máxima en horas (default: 1)

        Returns:
            True si existen predicciones frescas, False en caso contrario
        """
        return self.check_recent_predictions(symbol, hours_old=max_age_hours)

    def cleanup_old_predictions(self, symbol: str) -> int:
        """
        Elimina predicciones que ya pasaron (open_time < AHORA).

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)

        Returns:
            Número de predicciones eliminadas
        """
        try:
            collection_name = f"prediccion_klines_{symbol}"
            collection = self.db[collection_name]

            # Eliminar predicciones cuyo open_time ya pasó
            now = datetime.now(pytz.UTC)
            now_timestamp = int(now.timestamp() * 1000)

            query = {
                "open_time": {
                    "$lt": now_timestamp
                }
            }

            result = collection.delete_many(query)
            deleted_count = result.deleted_count

            if deleted_count > 0:
                logger.info(f"Predicciones viejas eliminadas para {symbol}: {deleted_count} registros")

            return deleted_count

        except Exception as e:
            logger.error(f"Error al limpiar predicciones viejas para {symbol}: {e}")
            return 0

    def get_last_prediction_hour_today(self, symbol: str) -> Optional[int]:
        """
        Obtiene la última hora del día que tiene predicciones.

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)

        Returns:
            Número de hora (0-23) de la última predicción del día, o None si no hay predicciones hoy
        """
        try:
            collection_name = f"prediccion_klines_{symbol}"
            collection = self.db[collection_name]

            # Calcular inicio y fin del día actual en UTC
            now = datetime.now(pytz.UTC)
            start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_today = now.replace(hour=23, minute=59, second=59, microsecond=999999)

            start_timestamp = int(start_of_today.timestamp() * 1000)
            end_timestamp = int(end_of_today.timestamp() * 1000)

            # Buscar predicciones del día actual, ordenadas por close_time descendente
            # IMPORTANTE: Usar close_time para detectar la última hora COMPLETADA
            # El horizonte 60 de hora N tiene open_time=N:30 pero close_time=N:59
            query = {
                "close_time": {
                    "$gte": start_timestamp,
                    "$lte": end_timestamp
                }
            }

            # Obtener la predicción con close_time más reciente
            latest_prediction = collection.find_one(
                query,
                sort=[("close_time", -1)]  # Descendente
            )

            if not latest_prediction:
                logger.info(f"No hay predicciones para {symbol} en el día de hoy")
                return None

            # Extraer la hora del close_time (hora completada)
            prediction_close_time = datetime.fromtimestamp(
                latest_prediction['close_time'] / 1000,
                tz=pytz.UTC
            )
            hour = prediction_close_time.hour

            logger.info(f"Última predicción de {symbol} hoy: hora {hour}:00 ({prediction_close_time})")
            return hour

        except Exception as e:
            logger.error(f"Error obteniendo última hora de predicción para {symbol}: {e}", exc_info=True)
            return None

    def check_real_data_available_until(self, symbol: str, target_hour: int) -> bool:
        """
        Verifica si existen datos reales hasta la hora target (inclusive).

        Ejemplo: target_hour=8 → verificar que existan datos hasta 08:59:59

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)
            target_hour: Hora objetivo (0-23)

        Returns:
            True si existen datos reales hasta target_hour:59:59, False en caso contrario
        """
        try:
            collection_name = f"klines_{symbol}"
            collection = self.db[collection_name]

            # Calcular timestamp del INICIO de la hora target (HH:00:00)
            # Para predecir hora N (N:00-N+1:00), solo necesitamos datos hasta N:00
            now = datetime.now(pytz.UTC)
            target_time = now.replace(
                hour=target_hour,
                minute=0,
                second=0,
                microsecond=0
            )

            # Si la hora target es en el futuro, ajustar a ayer
            if target_time > now:
                target_time = target_time - timedelta(days=1)

            target_timestamp = int(target_time.timestamp() * 1000)

            # Buscar el dato más reciente en la base de datos
            latest_data = collection.find_one(
                {},
                sort=[("open_time", -1)]  # Descendente
            )

            if not latest_data:
                logger.warning(f"No hay datos reales para {symbol}")
                return False

            latest_timestamp = latest_data['open_time']
            latest_time = datetime.fromtimestamp(latest_timestamp / 1000, tz=pytz.UTC)

            # Verificar si el último dato disponible >= target_time
            data_available = latest_timestamp >= target_timestamp

            if data_available:
                logger.info(f"✓ Datos reales disponibles para {symbol} hasta hora {target_hour} (último: {latest_time})")
            else:
                logger.info(f"✗ Datos reales NO disponibles para {symbol} hasta hora {target_hour} (último: {latest_time})")

            return data_available

        except Exception as e:
            logger.error(f"Error verificando datos reales para {symbol}: {e}", exc_info=True)
            return False

    def get_real_close_at_time(self, symbol: str, timestamp: datetime) -> Optional[float]:
        """
        Obtiene el precio de cierre real en un timestamp específico.

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)
            timestamp: Timestamp del que obtener el close

        Returns:
            Precio de cierre real, o None si no existe
        """
        try:
            collection_name = f"klines_{symbol}"
            collection = self.db[collection_name]

            # Asegurar que timestamp tiene zona horaria
            if timestamp.tzinfo is None:
                timestamp = pytz.UTC.localize(timestamp)

            timestamp_ms = int(timestamp.timestamp() * 1000)

            # Buscar dato exacto
            query = {"open_time": timestamp_ms}
            data = collection.find_one(query)

            if data:
                close_price = float(data['close'])
                logger.debug(f"Close real de {symbol} en {timestamp}: ${close_price:.2f}")
                return close_price
            else:
                logger.warning(f"No hay dato real para {symbol} en {timestamp}")
                return None

        except Exception as e:
            logger.error(f"Error obteniendo close real para {symbol}: {e}", exc_info=True)
            return None

    def get_prediction_close_at_time(self, symbol: str, timestamp: datetime) -> Optional[float]:
        """
        Obtiene el precio de cierre predicho en un timestamp específico.

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)
            timestamp: Timestamp del que obtener el close predicho

        Returns:
            Precio de cierre predicho, o None si no existe
        """
        try:
            collection_name = f"prediccion_klines_{symbol}"
            collection = self.db[collection_name]

            # Asegurar que timestamp tiene zona horaria
            if timestamp.tzinfo is None:
                timestamp = pytz.UTC.localize(timestamp)

            timestamp_ms = int(timestamp.timestamp() * 1000)

            # Buscar predicción exacta
            query = {"open_time": timestamp_ms}
            prediction = collection.find_one(query)

            if prediction:
                close_price = float(prediction['close'])
                logger.debug(f"Close predicho de {symbol} en {timestamp}: ${close_price:.2f}")
                return close_price
            else:
                logger.warning(f"No hay predicción para {symbol} en {timestamp}")
                return None

        except Exception as e:
            logger.error(f"Error obteniendo close predicho para {symbol}: {e}", exc_info=True)
            return None

    def check_predictions_for_hour(self, symbol: str, hour: int) -> bool:
        """
        Verifica si ya existen predicciones COMPLETAS para una hora específica del día actual.

        COMPLETAS = 12 predicciones (una por cada horizonte: 1,2,3,4,5,6,10,12,15,20,30,60)

        Args:
            symbol: Símbolo de la moneda (ej: btcusdt)
            hour: Hora del día (0-23)

        Returns:
            True si existen las 12 predicciones para esa hora, False en caso contrario
        """
        try:
            collection_name = f"prediccion_klines_{symbol}"
            collection = self.db[collection_name]

            # Calcular inicio de la hora
            now = datetime.now(pytz.UTC)
            hour_start = now.replace(hour=hour, minute=0, second=0, microsecond=0)

            # El primer horizonte empieza en hour_start (open_time = hour:00)
            first_horizon_timestamp = int(hour_start.timestamp() * 1000)

            # Verificar que exista predicción con open_time = hour:00 (primer horizonte)
            query = {
                "open_time": first_horizon_timestamp
            }

            count = collection.count_documents(query)

            # Deben haber exactamente 12 predicciones con open_time = hour:00
            # (una para cada horizonte que empieza en esa hora)
            expected_predictions = 12
            has_complete_predictions = (count == expected_predictions)

            if has_complete_predictions:
                logger.debug(f"✓ Predicciones COMPLETAS para {symbol} hora {hour}: {count}/{expected_predictions} registros")
            else:
                logger.debug(f"✗ Predicciones INCOMPLETAS para {symbol} hora {hour}: {count}/{expected_predictions} registros")

            return has_complete_predictions

        except Exception as e:
            logger.error(f"Error verificando predicciones para {symbol} hora {hour}: {e}", exc_info=True)
            return False

    def close(self):
        """Cierra la conexión con MongoDB."""
        if self.client:
            self.client.close()
            logger.info("Conexión con MongoDB cerrada")
