"""
Predictor LSTM Multi-Horizonte - NUEVA ARQUITECTURA.

Este módulo implementa la estrategia de predicción multi-horizonte donde:
- Se entrenan MÚLTIPLES modelos independientes (uno por cada horizonte temporal)
- Cada modelo predice un intervalo específico sin solapamiento
- Los horizontes cubren exactamente los próximos 60 minutos particionados

Horizontes: [1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60] minutos
Intervalos sin solapamiento: [0,1), [1,2), [2,3), ..., [30,60)

Referencia: condiciones.txt secciones 4, 5, 6
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras import backend as K
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import pytz
import gc
from logger_config import setup_logger
import config
from data_processor import DataProcessor

logger = setup_logger(__name__, config.LOG_DIR, config.LOG_LEVEL)


class LSTMPredictor:
    """
    Predictor basado en LSTM para estrategia multi-horizonte.

    Características principales:
    - Entrena 12 modelos independientes (uno por horizonte)
    - Cada modelo predice una "vela agregada" para su intervalo
    - Usa features con resampling multi-escala
    - Predicciones sin solapamiento cubriendo 60 minutos
    """

    def __init__(self):
        """Inicializa el predictor multi-horizonte."""
        self.data_processor = DataProcessor()

        # Diccionario de modelos: {horizon: model}
        self.models = {}

        # Diccionario de scalers: {horizon: scaler}
        self.scalers = {}

        # Horizontes configurados
        self.horizons = config.PREDICTION_HORIZONS

        # Columnas input y target
        self.input_columns = config.INPUT_COLUMNS
        self.target_columns = config.TARGET_COLUMNS

        logger.info(f"LSTMPredictor inicializado para {len(self.horizons)} horizontes")
        logger.info(f"Horizontes: {self.horizons}")

    def build_lstm_model(self, n_features: int, n_targets: int) -> keras.Model:
        """
        Construye la arquitectura LSTM para un horizonte.

        Arquitectura:
        - 2 capas LSTM bidireccionales
        - Dropout para regularización
        - BatchNormalization
        - Capas densas finales

        Args:
            n_features: Número de features de entrada
            n_targets: Número de valores target (columnas OHLCV)

        Returns:
            Modelo Keras compilado
        """
        model = keras.Sequential([
            # Primera capa LSTM
            layers.LSTM(
                config.LSTM_UNITS,
                return_sequences=True,
                input_shape=(1, n_features),  # (timesteps=1, features)
                kernel_regularizer=keras.regularizers.l2(0.01)
            ),
            layers.Dropout(config.DROPOUT_RATE),
            layers.BatchNormalization(),

            # Segunda capa LSTM
            layers.LSTM(
                config.LSTM_UNITS // 2,
                return_sequences=False,
                kernel_regularizer=keras.regularizers.l2(0.01)
            ),
            layers.Dropout(config.DROPOUT_RATE),
            layers.BatchNormalization(),

            # Capas densas
            layers.Dense(64, activation='relu'),
            layers.Dropout(0.1),
            layers.Dense(32, activation='relu'),

            # Capa de salida (predice OHLCV de la vela agregada)
            layers.Dense(n_targets)
        ])

        # Compilar con optimizer Adam
        optimizer = keras.optimizers.Adam(learning_rate=config.LEARNING_RATE)
        model.compile(
            optimizer=optimizer,
            loss='mse',
            metrics=['mae']
        )

        return model

    def train_models_for_all_horizons(
        self,
        symbol: str,
        all_data: List[Dict]
    ) -> Dict[int, Dict]:
        """
        Entrena modelos independientes para TODOS los horizontes con VENTANAS VARIABLES.

        NUEVA ESTRATEGIA:
        - Cada horizonte usa su propia ventana de datos específica
        - Horizontes 1-6: 2880 minutos (2 días)
        - Horizontes 10-15: 4320 minutos (3 días)
        - Horizontes 20-30: 5760 minutos (4 días)
        - Horizonte 60: 8640 minutos (6 días)

        Para cada horizonte:
        1. Obtener ventana específica según HORIZON_TRAINING_WINDOWS
        2. Construye dataset supervisado con data_processor
        3. Normaliza features y targets
        4. Entrena modelo LSTM específico
        5. Guarda modelo y scaler

        Args:
            symbol: Símbolo de la moneda
            all_data: TODOS los datos históricos disponibles

        Returns:
            Diccionario con métricas por horizonte: {horizon: metrics}
        """
        logger.info("="*80)
        logger.info(f"ENTRENAMIENTO MULTI-HORIZONTE CON VENTANAS VARIABLES - {symbol.upper()}")
        logger.info("="*80)
        logger.info(f"Datos históricos disponibles: {len(all_data)} minutos")
        logger.info(f"Horizontes a entrenar: {self.horizons}")
        logger.info("")
        logger.info("Ventanas de entrenamiento por horizonte:")
        for h in self.horizons:
            w = config.HORIZON_TRAINING_WINDOWS[h]
            logger.info(f"  Horizonte {h:2d} min → {w:4d} min ({w/1440:.1f} días)")
        logger.info("="*80)

        all_metrics = {}

        for horizon in self.horizons:
            # Obtener ventana específica para este horizonte
            window_size = config.HORIZON_TRAINING_WINDOWS[horizon]

            logger.info(f"\n{'='*60}")
            logger.info(f"HORIZONTE {horizon} MINUTOS")
            logger.info(f"Ventana de entrenamiento: {window_size} minutos ({window_size/1440:.1f} días)")
            logger.info(f"{'='*60}")

            try:
                # 1. Determinar ventana específica para este horizonte
                logger.info(f"Determinando ventana de {window_size} minutos...")
                lower_bound, reference_time, window_data = self.data_processor.determine_training_window(
                    all_data,
                    window_size
                )

                logger.info(f"✓ Ventana determinada:")
                logger.info(f"  Lower bound: {lower_bound}")
                logger.info(f"  Reference time: {reference_time}")
                logger.info(f"  Datos: {len(window_data)} minutos")

                # 2. Crear dataset supervisado para este horizonte
                logger.info(f"Creando dataset supervisado...")
                X, y = self.data_processor.create_supervised_dataset(
                    window_data,
                    reference_time,
                    horizon
                )

                if len(X) == 0 or len(y) == 0:
                    logger.error(f"Dataset vacío para horizonte {horizon}")
                    continue

                logger.info(f"✓ Dataset creado: X={X.shape}, y={y.shape}")

                # 3. Normalizar features y targets con SCALERS SEPARADOS
                # CRÍTICO: Features y targets tienen rangos MUY diferentes
                # - Features: valores absolutos de precio (~$90,000-$92,000)
                # - Targets: deltas/variaciones (+/-$100-$500 típicamente)
                # Usar el mismo scaler causa desnormalización incorrecta

                n_features = X.shape[1]
                n_targets = y.shape[1]

                # Scaler SEPARADO para features
                scaler_X = MinMaxScaler(feature_range=(0, 1))
                X_scaled = scaler_X.fit_transform(X)

                # Scaler SEPARADO para targets (deltas)
                scaler_y = MinMaxScaler(feature_range=(0, 1))
                y_scaled = scaler_y.fit_transform(y)

                # Guardar AMBOS scalers para este horizonte como tupla
                self.scalers[horizon] = (scaler_X, scaler_y)

                logger.info(f"✓ Scalers creados:")
                logger.info(f"  Features X: min={scaler_X.data_min_[:5]}, max={scaler_X.data_max_[:5]}")
                logger.info(f"  Targets y: min={scaler_y.data_min_}, max={scaler_y.data_max_}")

                # 4. Reshape para LSTM: (samples, timesteps=1, features)
                X_reshaped = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))

                logger.info(f"✓ Datos normalizados y reshape: X={X_reshaped.shape}, y={y_scaled.shape}")

                # 5. Construir modelo LSTM
                model = self.build_lstm_model(n_features, n_targets)

                logger.info(f"✓ Modelo construido:")
                logger.info(f"  Features: {n_features}, Targets: {n_targets}")
                logger.info(f"  LSTM units: {config.LSTM_UNITS}, Layers: {config.LSTM_LAYERS}")

                # 6. Callbacks
                callbacks = [
                    keras.callbacks.EarlyStopping(
                        monitor='val_loss',
                        patience=10,
                        restore_best_weights=True,
                        verbose=1
                    ),
                    keras.callbacks.ReduceLROnPlateau(
                        monitor='val_loss',
                        factor=0.5,
                        patience=5,
                        min_lr=0.00001,
                        verbose=1
                    )
                ]

                # 7. Entrenar modelo
                logger.info(f"Iniciando entrenamiento...")
                logger.info(f"  Epochs: {config.EPOCHS}, Batch size: {config.BATCH_SIZE}")
                logger.info(f"  Validation split: {config.VALIDATION_SPLIT}")
                history = model.fit(
                    X_reshaped,
                    y_scaled,
                    epochs=config.EPOCHS,
                    batch_size=config.BATCH_SIZE,
                    validation_split=config.VALIDATION_SPLIT,
                    verbose=1,
                    callbacks=callbacks
                )

                # 8. Guardar modelo
                self.models[horizon] = model

                # 9. Extraer métricas
                metrics = self._extract_metrics_from_history(history, horizon)
                all_metrics[horizon] = metrics

                logger.info(f"✓ Modelo entrenado para horizonte {horizon}")
                logger.info(f"  Métricas: {metrics}")

            except Exception as e:
                logger.error(f"Error entrenando modelo para horizonte {horizon}: {e}", exc_info=True)
                all_metrics[horizon] = {'error': str(e)}

        logger.info("\n" + "="*80)
        logger.info(f"RESUMEN ENTRENAMIENTO - {symbol.upper()}")
        logger.info("="*80)
        logger.info(f"Modelos entrenados: {len(self.models)}/{len(self.horizons)}")
        logger.info(f"Scalers creados: {len(self.scalers)}")
        logger.info("")
        logger.info("Métricas por horizonte:")
        for horizon in sorted(all_metrics.keys()):
            metrics = all_metrics[horizon]
            window_size = config.HORIZON_TRAINING_WINDOWS[horizon]
            if 'error' not in metrics:
                logger.info(f"  H{horizon:2d} ({window_size:4d}min): "
                          f"val_loss={metrics.get('val_loss', 0):.6f}, "
                          f"epochs={metrics.get('best_epoch', 0)}/{metrics.get('total_epochs', 0)}")
            else:
                logger.info(f"  H{horizon:2d} ({window_size:4d}min): ERROR - {metrics['error']}")
        logger.info("="*80)

        return all_metrics

    def _extract_metrics_from_history(self, history, horizon: int) -> Dict:
        """
        Extrae métricas del historial de entrenamiento.

        Args:
            history: Objeto History de Keras
            horizon: Horizonte temporal

        Returns:
            Diccionario con métricas
        """
        try:
            # Obtener la mejor época (mínimo val_loss)
            best_epoch = np.argmin(history.history['val_loss'])

            metrics = {
                'horizon': horizon,
                'best_epoch': int(best_epoch + 1),
                'total_epochs': len(history.history['loss']),
                'train_loss': float(history.history['loss'][best_epoch]),
                'val_loss': float(history.history['val_loss'][best_epoch]),
                'train_mae': float(history.history.get('mae', [0])[best_epoch]) if 'mae' in history.history else 0,
                'val_mae': float(history.history.get('val_mae', [0])[best_epoch]) if 'val_mae' in history.history else 0,
            }

            # Calcular mejora
            initial_loss = float(history.history['loss'][0])
            final_loss = metrics['train_loss']
            if initial_loss > 0:
                improvement_pct = ((initial_loss - final_loss) / initial_loss) * 100
                metrics['improvement_pct'] = float(improvement_pct)

            return metrics

        except Exception as e:
            logger.error(f"Error extrayendo métricas: {e}", exc_info=True)
            return {}

    def predict_next_60_minutes(
        self,
        recent_data: List[Dict],
        reference_time: datetime,
        mongo_client = None,
        symbol: str = None
    ) -> List[Dict]:
        """
        Genera predicciones para los próximos 60 minutos usando los 12 modelos.

        NUEVA ESTRATEGIA CON VARIACIONES - 60 PREDICCIONES INDIVIDUALES:
        1. Los modelos predicen VARIACIONES (deltas) no valores absolutos
        2. Para cada minuto se obtiene el close REAL anterior (continuidad)
        3. Se aplican las variaciones predichas al close anterior
        4. Se garantiza: open(n) = close(n-1) REAL

        ALGORITMO:
        1. Para cada horizonte (en orden):
           a. Preparar features usando data_processor
           b. Normalizar con el scaler del horizonte
           c. Predecir VARIACIONES con el modelo
           d. Desnormalizar predicción de variaciones
           e. Construir velas individuales aplicando variaciones

        2. CADA HORIZONTE GENERA PREDICCIONES PARA CADA MINUTO EN SU INTERVALO:
           - Horizonte 1: [0, 1) min → 1 predicción de 1 minuto (minuto 0)
           - Horizonte 2: [1, 2) min → 1 predicción de 1 minuto (minuto 1)
           - Horizonte 6: [5, 6) min → 1 predicción de 1 minuto (minuto 5)
           - Horizonte 10: [6, 10) min → 4 predicciones de 1 minuto (minutos 6,7,8,9)
           - Horizonte 60: [30, 60) min → 30 predicciones de 1 minuto (minutos 30-59)
           TOTAL: 60 predicciones por hora (una por cada minuto 0-59)

        Args:
            recent_data: Últimos N minutos de datos (según horizonte)
            reference_time: Tiempo de referencia (hora redonda desde donde predecir)
            mongo_client: Cliente MongoDB para obtener datos reales (opcional)

        Returns:
            Lista de 60 predicciones (documentos con OHLCV + metadata)
        """
        logger.info("="*80)
        logger.info("GENERACIÓN DE PREDICCIONES MULTI-HORIZONTE CON VARIACIONES")
        logger.info("="*80)
        logger.info(f"Reference time: {reference_time}")
        logger.info(f"Datos disponibles: {len(recent_data)} minutos")

        # Validar que tengamos todos los modelos
        if len(self.models) != len(self.horizons):
            logger.error(f"Faltan modelos. Esperados: {len(self.horizons)}, Disponibles: {len(self.models)}")
            return []

        all_predictions = []

        # Preparar features una sola vez (son las mismas para todos los modelos)
        try:
            prediction_features = self.data_processor.prepare_prediction_features(recent_data)
            logger.info(f"Features de predicción preparadas: {prediction_features.shape}")
        except Exception as e:
            logger.error(f"Error preparando features: {e}", exc_info=True)
            return []

        # Obtener el último close REAL disponible
        # IMPORTANTE: Solo predecir si existe el dato REAL de reference_time
        # Si no existe, retornar lista vacía para esperar al siguiente ciclo

        # Intentar obtener el dato REAL de la hora actual (reference_time) desde MongoDB
        if not mongo_client or not symbol:
            logger.error("MongoDB client o símbolo no disponibles. No se puede verificar dato real.")
            return []

        try:
            # El dato de reference_time tendría open_time = reference_time
            reference_time_ms = int(reference_time.timestamp() * 1000)
            real_data_at_reference = mongo_client.get_kline_by_open_time(symbol, reference_time_ms)

            if not real_data_at_reference:
                logger.warning(f"⏳ Dato REAL en reference_time ({reference_time}) NO disponible aún.")
                logger.warning(f"⏳ Esperando al siguiente ciclo para generar predicciones...")
                return []  # Retornar vacío para esperar

            # Usar el close REAL de la hora actual como punto de partida
            last_real_close = float(real_data_at_reference['close'])
            last_real_time = reference_time
            logger.info(f"✓ Dato REAL encontrado en reference_time: ${last_real_close:.2f} (tiempo: {last_real_time})")

        except Exception as e:
            logger.error(f"Error buscando dato real en reference_time: {e}")
            return []  # Retornar vacío si hay error

        logger.info(f"Último close REAL para predicciones: ${last_real_close:.2f} (tiempo: {last_real_time})")

        # Cache de predicciones previas para continuidad
        predictions_cache = {}

        # Predecir con cada modelo (uno por horizonte)
        for horizon in self.horizons:
            logger.info(f"\nPrediciendo horizonte {horizon} minutos...")

            try:
                # Obtener modelo y scalers para este horizonte
                model = self.models.get(horizon)
                scalers = self.scalers.get(horizon)

                if model is None or scalers is None:
                    logger.error(f"Modelo o scalers no disponibles para horizonte {horizon}")
                    continue

                # Desempaquetar scalers (scaler_X para features, scaler_y para targets)
                scaler_X, scaler_y = scalers

                # Normalizar features con scaler_X
                features_scaled = scaler_X.transform(prediction_features)

                # Reshape para LSTM: (1, timesteps=1, features)
                features_reshaped = features_scaled.reshape((1, 1, features_scaled.shape[1]))

                # Predecir VARIACIONES (deltas) - salida normalizada
                prediction_scaled = model.predict(features_reshaped, verbose=0)[0]

                # Desnormalizar predicción de DELTAS con scaler_y (NO scaler_X)
                # prediction_scaled tiene shape (n_targets,)
                # Reshape para inverse_transform: (1, n_targets)
                prediction_denorm = scaler_y.inverse_transform(
                    prediction_scaled.reshape(1, -1)
                )[0]

                # Las predicciones son VARIACIONES
                predicted_deltas = {
                    'close_delta': float(prediction_denorm[0]),  # Cambio en close
                    'high_delta': float(prediction_denorm[1]),   # Diferencia high - close_anterior
                    'low_delta': float(prediction_denorm[2]),    # Diferencia low - close_anterior
                    'volume': float(prediction_denorm[3])        # Volumen total
                }

                # Liberar memoria de arrays temporales inmediatamente
                del features_scaled, features_reshaped, prediction_scaled, prediction_denorm

                logger.info(f"  Deltas predichos: close={predicted_deltas['close_delta']:.4f}, "
                          f"high={predicted_deltas['high_delta']:.4f}, low={predicted_deltas['low_delta']:.4f}")

                # Obtener intervalo del horizonte
                interval_start, interval_end = config.HORIZON_INTERVALS[horizon]
                interval_duration_minutes = interval_end - interval_start

                # ==========================================
                # GENERAR PREDICCIÓN AGREGADA POR HORIZONTE
                # ==========================================
                # IMPORTANTE: Todas las predicciones de una hora tienen el MISMO open_time (hora redonda)
                # Solo el close_time varía según el intervalo del horizonte
                # Ejemplo: Para la hora 13:00-14:00, TODAS las predicciones tienen open_time = 13:00
                # ==========================================

                # TODAS las predicciones tienen open_time = reference_time (hora redonda)
                open_time_ms = int(reference_time.timestamp() * 1000)

                # El close_time depende del fin del intervalo del horizonte
                close_time = reference_time + timedelta(minutes=interval_end) - timedelta(milliseconds=1)
                close_time_ms = int(close_time.timestamp() * 1000)

                # Obtener close anterior
                if interval_start == 0:
                    # Primer intervalo: usar último close real disponible
                    prev_close = last_real_close
                else:
                    # Intervalos subsecuentes: buscar en predicciones previas
                    prev_interval_time = reference_time + timedelta(minutes=interval_start - 1)
                    prev_time_ms = int(prev_interval_time.timestamp() * 1000)

                    # Buscar en predicciones previas el close anterior
                    prev_close = last_real_close
                    for pred in all_predictions:
                        if pred['close_time'] >= prev_time_ms:
                            prev_close = pred['close']
                            break

                # Aplicar variaciones al close anterior
                predicted_close = prev_close + predicted_deltas['close_delta']
                predicted_high = prev_close + predicted_deltas['high_delta']
                predicted_low = prev_close + predicted_deltas['low_delta']

                # Construir vela agregada predicha con continuidad
                predicted_candle = {
                    'open': prev_close,  # CONTINUIDAD: open(n) = close(n-1)
                    'high': predicted_high,
                    'low': predicted_low,
                    'close': predicted_close,
                    'volume': predicted_deltas['volume']
                }

                # Validar coherencia OHLC
                predicted_candle = self._validate_ohlc(predicted_candle)

                # Crear documento de predicción agregada
                prediction_doc = {
                    'open_time': open_time_ms,
                    'open': predicted_candle['open'],
                    'high': predicted_candle['high'],
                    'low': predicted_candle['low'],
                    'close': predicted_candle['close'],
                    'volume': predicted_candle['volume'],
                    'close_time': close_time_ms,
                    'predicted_at': datetime.now(pytz.UTC).isoformat(),
                    'minutes_ahead': horizon  # Horizonte usado (1, 2, 3, ..., 60)
                }

                all_predictions.append(prediction_doc)

                logger.info(f"✓ Horizonte {horizon}: intervalo [{interval_start}, {interval_end}) minutos = 1 predicción agregada de {interval_duration_minutes} minuto(s)")

            except Exception as e:
                logger.error(f"Error prediciendo horizonte {horizon}: {e}", exc_info=True)
                continue

        # Ordenar predicciones por timestamp
        all_predictions.sort(key=lambda x: x['open_time'])

        logger.info("\n" + "="*80)
        logger.info("RESUMEN DE PREDICCIONES AGREGADAS POR HORIZONTE")
        logger.info("="*80)
        logger.info(f"Total predicciones generadas: {len(all_predictions)} (1 por horizonte)")
        if all_predictions:
            first_pred = datetime.fromtimestamp(all_predictions[0]['open_time']/1000, tz=pytz.UTC)
            last_pred = datetime.fromtimestamp(all_predictions[-1]['open_time']/1000, tz=pytz.UTC)
            logger.info(f"Primera predicción: {first_pred}")
            logger.info(f"  Horizonte usado: {all_predictions[0]['minutes_ahead']} minutos")
            logger.info(f"  Open=${all_predictions[0]['open']:.2f} (= close anterior)")
            logger.info(f"Última predicción: {last_pred}")
            logger.info(f"  Horizonte usado: {all_predictions[-1]['minutes_ahead']} minutos")
            logger.info(f"  Close=${all_predictions[-1]['close']:.2f}")
        logger.info("="*80)

        # LIMPIEZA DE MEMORIA LIGERA
        # Forzar garbage collection para liberar tensores temporales
        # NO usamos K.clear_session() aquí porque destruiría los modelos cargados
        try:
            gc.collect()
        except Exception as e:
            logger.warning(f"Error durante garbage collection: {e}")

        return all_predictions

    def _validate_ohlc(self, candle: Dict) -> Dict:
        """
        Valida y corrige coherencia de valores OHLC.

        Reglas:
        - high >= max(open, close)
        - low <= min(open, close)
        - volume >= 0

        Args:
            candle: Diccionario con valores OHLCV

        Returns:
            Diccionario con valores validados
        """
        open_val = candle['open']
        high_val = candle['high']
        low_val = candle['low']
        close_val = candle['close']
        volume_val = candle['volume']

        # Validar high
        max_price = max(open_val, close_val)
        if high_val < max_price:
            high_val = max_price

        # Validar low
        min_price = min(open_val, close_val)
        if low_val > min_price:
            low_val = min_price

        # Validar volume
        if volume_val < 0:
            volume_val = 0

        return {
            'open': open_val,
            'high': high_val,
            'low': low_val,
            'close': close_val,
            'volume': volume_val
        }

    def load_models(self, models_dict: Dict[int, keras.Model], scalers_dict: Dict[int, MinMaxScaler]):
        """
        Carga modelos y scalers previamente entrenados.

        Args:
            models_dict: Diccionario {horizon: model}
            scalers_dict: Diccionario {horizon: scaler}
        """
        self.models = models_dict
        self.scalers = scalers_dict

        logger.info(f"Modelos cargados: {list(self.models.keys())}")
        logger.info(f"Scalers cargados: {list(self.scalers.keys())}")

        # Validar que tengamos todos los horizontes
        missing_models = set(self.horizons) - set(self.models.keys())
        missing_scalers = set(self.horizons) - set(self.scalers.keys())

        if missing_models:
            logger.warning(f"Faltan modelos para horizontes: {missing_models}")
        if missing_scalers:
            logger.warning(f"Faltan scalers para horizontes: {missing_scalers}")
