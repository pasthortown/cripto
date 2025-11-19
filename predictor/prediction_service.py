"""
Servicio de predicción multi-horizonte - NUEVA ARQUITECTURA.

Este servicio orquesta el proceso de predicción CADA HORA:
1. Verifica si ya existen predicciones para la hora actual
2. Obtiene/entrena modelos multi-horizonte si no existen o están obsoletos
3. Genera predicciones para los próximos 60 minutos particionados
4. Guarda en MongoDB con campo 'minutes_ahead' correcto

Referencia: condiciones.txt secciones 1-7
"""

from datetime import datetime, timedelta
import pytz
import time
import gc
from typing import List, Optional, Tuple, Dict
from tensorflow.keras import backend as K
from logger_config import setup_logger
import config
from mongo_client import MongoDBClient
from lstm_predictor import LSTMPredictor
from model_manager import ModelManager
from data_processor import DataProcessor

logger = setup_logger(__name__, config.LOG_DIR, config.LOG_LEVEL)


class PredictionService:
    """
    Servicio que gestiona predicciones multi-horizonte CADA HORA.

    Flujo principal:
    1. Ejecuta cada hora en punto (ej: 13:00, 14:00, etc.)
    2. Para cada símbolo:
       a. Verifica si ya hay predicciones para esta hora
       b. Si no hay modelos válidos, entrena 12 modelos (uno por horizonte)
       c. Genera predicciones para los próximos 60 minutos usando algoritmo específico
       d. Guarda predicciones en MongoDB
    """

    def __init__(self):
        """Inicializa el servicio de predicción."""
        self.mongo_client = MongoDBClient()
        self.model_manager = ModelManager()
        self.data_processor = DataProcessor()

        logger.info("="*80)
        logger.info("SERVICIO DE PREDICCIÓN MULTI-HORIZONTE INICIALIZADO")
        logger.info("="*80)
        logger.info(f"Estrategia: {len(config.PREDICTION_HORIZONS)} modelos por símbolo")
        logger.info(f"Horizontes: {config.PREDICTION_HORIZONS}")
        logger.info(f"Ventanas variables: {min(config.HORIZON_TRAINING_WINDOWS.values())}-{max(config.HORIZON_TRAINING_WINDOWS.values())} minutos")
        logger.info(f"Bucle continuo: Cada {config.VALIDATION_INTERVAL_SECONDS} segundos")
        logger.info("="*80)

    def get_last_prediction_hour_today(self, symbol: str) -> Optional[int]:
        """
        Obtiene la última hora del día que tiene predicciones.

        Args:
            symbol: Símbolo de la moneda

        Returns:
            Número de hora (0-23) o None si no hay predicciones hoy
        """
        return self.mongo_client.get_last_prediction_hour_today(symbol)

    def check_real_data_available_until(self, symbol: str, target_hour: int) -> bool:
        """
        Verifica si existen datos reales hasta la hora target (inclusive).

        Args:
            symbol: Símbolo de la moneda
            target_hour: Hora objetivo (0-23)

        Returns:
            True si existen datos reales hasta target_hour:59:59
        """
        return self.mongo_client.check_real_data_available_until(symbol, target_hour)

    def check_exact_hour_data_exists(self, symbol: str, target_hour: int) -> bool:
        """
        Verifica si existe el dato REAL EXACTO de la hora target_hour:00.

        IMPORTANTE: Para predecir 22:00-23:00, necesitamos que exista el dato
        con open_time = 22:00:00 (no solo datos hasta 21:59).

        Args:
            symbol: Símbolo de la moneda
            target_hour: Hora objetivo (0-23)

        Returns:
            True si existe el dato con open_time = target_hour:00:00
        """
        now = datetime.now(pytz.UTC)
        target_time = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
        target_timestamp = int(target_time.timestamp() * 1000)

        # Buscar el dato específico con open_time = target_time
        kline = self.mongo_client.get_kline_by_open_time(symbol, target_timestamp)

        if kline:
            logger.info(f"✓ Dato REAL de {symbol} hora {target_hour}:00 existe (close: {kline['close']})")
            return True
        else:
            logger.debug(f"✗ Dato REAL de {symbol} hora {target_hour}:00 NO existe aún")
            return False

    def predict_hour_interval(self, symbol: str, start_hour: int) -> bool:
        """
        Predice intervalo de 1 hora FUTURA: [start_hour:00, start_hour+1:00)

        IMPORTANTE: Genera predicciones para la SIGUIENTE hora completa.
        Ejemplo: Si ahora son las 22:38, start_hour=23 → predecir de 23:00 a 23:59

        Las predicciones comienzan en hora redonda (start_hour:00) y se basan en datos
        reales disponibles hasta start_hour-1:59 (hora anterior completa).

        Args:
            symbol: Símbolo de la moneda
            start_hour: Hora de inicio del intervalo (0-23)

        Returns:
            True si se generaron predicciones exitosamente
        """
        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"PREDICIENDO INTERVALO HORARIO FUTURO: {start_hour}:00 - {start_hour+1}:00")
            logger.info(f"Símbolo: {symbol.upper()}")
            logger.info(f"{'='*80}")

            # 1. Obtener o entrenar modelos
            logger.info(f"Obteniendo modelos para {symbol}...")
            predictor, is_new = self._get_or_train_models(symbol)

            if not predictor:
                logger.error(f"No se pudieron obtener modelos para {symbol}")
                return False

            if is_new:
                logger.info(f"✓ Modelos nuevos entrenados para {symbol}")
            else:
                logger.info(f"✓ Modelos existentes cargados para {symbol}")

            # 2. Determinar ventana de predicción para la hora específica
            # CRÍTICO: reference_time es el INICIO de la hora a predecir (hora redonda)
            # Los datos históricos deben ir HASTA reference_time (excluído)
            logger.info(f"Obteniendo datos históricos hasta hora {start_hour}:00...")

            now = datetime.now(pytz.UTC)
            reference_time = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)

            logger.info(f"Reference time (inicio de predicciones): {reference_time}")

            # Obtener todos los datos históricos hasta reference_time
            all_data = self.mongo_client.get_all_historical_data(symbol, end_time=reference_time)

            if not all_data:
                logger.error(f"No hay datos para predicción de {symbol} hasta {reference_time}")
                return False

            # Usar la ventana más grande para tener datos suficientes para todos los horizontes
            max_window_size = max(config.HORIZON_TRAINING_WINDOWS.values())

            # Verificar que tengamos suficientes datos
            if len(all_data) < max_window_size:
                logger.error(f"Datos insuficientes para {symbol}. Necesarios: {max_window_size}, Disponibles: {len(all_data)}")
                return False

            # Tomar los últimos max_window_size datos antes de reference_time
            window_data = all_data[-max_window_size:]

            logger.info(f"✓ Ventana de predicción determinada:")
            logger.info(f"  Reference time: {reference_time}")
            logger.info(f"  Datos históricos hasta reference_time: {len(all_data)} minutos")
            logger.info(f"  Ventana de entrenamiento: {len(window_data)} minutos ({max_window_size} max)")

            # 3. Generar predicciones para los próximos 60 minutos
            logger.info(f"Generando predicciones para intervalo {start_hour}:00...")

            predictions = predictor.predict_next_60_minutes(
                window_data,
                reference_time,
                mongo_client=self.mongo_client,
                symbol=symbol
            )

            if not predictions:
                logger.error(f"No se generaron predicciones para {symbol}")
                return False

            logger.info(f"✓ Predicciones generadas: {len(predictions)} minutos")

            # 4. Guardar predicciones en MongoDB
            logger.info(f"Guardando predicciones en MongoDB...")

            if not self.mongo_client.save_predictions(symbol, predictions):
                logger.error(f"Error guardando predicciones para {symbol}")
                return False

            logger.info(f"✓ Predicciones guardadas exitosamente")
            logger.info(f"✓ INTERVALO {start_hour}:00 COMPLETADO")
            logger.info(f"{'='*80}")

            return True

        except Exception as e:
            logger.error(f"Error prediciendo intervalo horario para {symbol}: {e}", exc_info=True)
            return False

    def check_predictions_for_current_hour(self, symbol: str) -> bool:
        """
        Verifica si ya existen predicciones para la hora actual.

        Args:
            symbol: Símbolo de la moneda

        Returns:
            True si ya existen predicciones para esta hora
        """
        try:
            now = datetime.now(pytz.UTC)
            # Truncar a hora redonda (inicio de la hora actual)
            current_hour = now.replace(minute=0, second=0, microsecond=0)

            # Calcular timestamp de inicio de la próxima hora (donde empiezan las predicciones)
            next_hour = current_hour + timedelta(hours=1)
            next_hour_ms = int(next_hour.timestamp() * 1000)

            # Buscar predicciones para el primer minuto de la próxima hora
            collection_name = f"prediccion_klines_{symbol}"
            collection = self.mongo_client.db[collection_name]

            count = collection.count_documents({"open_time": next_hour_ms})

            exists = count > 0

            if exists:
                logger.info(f"✓ Ya existen predicciones para {symbol} hora {next_hour}")
            else:
                logger.info(f"✗ No hay predicciones para {symbol} hora {next_hour}")

            return exists

        except Exception as e:
            logger.error(f"Error verificando predicciones para {symbol}: {e}", exc_info=True)
            return False

    def _get_or_train_models(self, symbol: str) -> Tuple[Optional[LSTMPredictor], bool]:
        """
        Obtiene modelos del día actual o entrena nuevos si no existen.

        LÓGICA (Sección 8):
        1. Verificar si existen modelos del DÍA ACTUAL
        2. Si SÍ → CARGAR (rápido ~2 segundos)
        3. Si NO → ENTRENAR (lento ~5 minutos, solo una vez al día)

        Args:
            symbol: Símbolo de la moneda

        Returns:
            Tupla (predictor, is_new)
            - predictor: LSTMPredictor con modelos cargados/entrenados
            - is_new: True si se entrenaron nuevos modelos
        """
        # Verificar si existen modelos válidos (del día actual)
        is_valid, paths_dict, date_str = self.model_manager.check_models_validity(symbol)

        if is_valid and paths_dict:
            # CARGAR modelos existentes
            logger.info(f"[{symbol}] ✓ Modelos válidos encontrados (fecha: {date_str})")
            logger.info(f"[{symbol}]   └─ Cargando modelos (rápido)...")

            try:
                models_dict, scalers_dict, metadata = self.model_manager.load_models(paths_dict)

                if models_dict and scalers_dict:
                    predictor = LSTMPredictor()
                    predictor.load_models(models_dict, scalers_dict)
                    logger.info(f"[{symbol}] ✓ 12 modelos cargados exitosamente")
                    return predictor, False
                else:
                    logger.warning(f"[{symbol}] Error al cargar modelos, entrenando nuevos...")

            except Exception as e:
                logger.error(f"[{symbol}] Error cargando modelos: {e}, entrenando nuevos...")

        # ENTRENAR nuevos modelos
        logger.info(f"[{symbol}] ⚠️  No hay modelos válidos para hoy")
        logger.info(f"[{symbol}]   └─ Entrenando 12 modelos (esto tomará ~5 minutos)...")

        # Limpiar modelos viejos antes de entrenar
        self.model_manager.cleanup_old_models(symbol)

        return self._train_new_models(symbol)

    def _train_new_models(self, symbol: str) -> Tuple[Optional[LSTMPredictor], bool]:
        """
        Entrena nuevos modelos multi-horizonte para un símbolo.

        ALGORITMO (según condiciones.txt sección 3):
        1. Obtener TODOS los datos históricos del símbolo
        2. Determinar ventana de 2880 minutos usando algoritmo específico
        3. Entrenar 12 modelos (uno por horizonte) con esa ventana
        4. Guardar modelos y scalers

        Args:
            symbol: Símbolo de la moneda

        Returns:
            Tupla (predictor, is_new)
        """
        try:
            logger.info("")
            logger.info("="*80)
            logger.info(f"[{symbol}] ENTRENANDO NUEVOS MODELOS")
            logger.info("="*80)

            # 1. Obtener TODOS los datos históricos disponibles
            logger.info(f"[{symbol}] Paso 1: Obteniendo datos históricos...")
            all_data = self.mongo_client.get_all_historical_data(symbol)

            if not all_data:
                logger.error(f"[{symbol}] No hay datos históricos")
                return None, False

            logger.info(f"[{symbol}]   └─ {len(all_data)} minutos disponibles")

            # 2. Entrenar modelos multi-horizonte CON VENTANAS VARIABLES
            logger.info(f"[{symbol}] Paso 2: Entrenando 12 modelos multi-horizonte...")
            predictor = LSTMPredictor()

            # Entrenar todos los modelos (cada uno con su ventana específica)
            metrics = predictor.train_models_for_all_horizons(
                symbol,
                all_data
            )

            if len(predictor.models) != len(config.PREDICTION_HORIZONS):
                logger.error(
                    f"[{symbol}] No se entrenaron todos los modelos. "
                    f"Esperados: {len(config.PREDICTION_HORIZONS)}, "
                    f"Entrenados: {len(predictor.models)}"
                )
                return None, False

            # Mostrar resumen de entrenamiento
            for horizon in config.PREDICTION_HORIZONS:
                window_size = config.HORIZON_TRAINING_WINDOWS[horizon]
                val_loss = metrics.get(horizon, {}).get('val_loss', 'N/A')
                if isinstance(val_loss, float):
                    logger.info(f"[{symbol}]   └─ H{horizon:2d}  ({window_size:4d} min): val_loss={val_loss:.4f} ✓")
                else:
                    logger.info(f"[{symbol}]   └─ H{horizon:2d}  ({window_size:4d} min): {val_loss}")

            # 3. Guardar modelos
            logger.info(f"[{symbol}] Paso 3: Guardando modelos...")
            metadata = {
                'training_metrics': metrics,
                'horizon_training_windows': config.HORIZON_TRAINING_WINDOWS,
                'trained_at': datetime.now(pytz.UTC).isoformat()
            }

            if self.model_manager.save_models(symbol, predictor.models, predictor.scalers, metadata):
                logger.info(f"[{symbol}] ✓ Modelos entrenados y guardados")
            else:
                logger.warning(f"[{symbol}] ⚠️  Modelos entrenados (no guardados, usará en memoria)")

            logger.info("="*80)
            logger.info(f"[{symbol}] ✓ ENTRENAMIENTO COMPLETADO")
            logger.info("="*80)
            logger.info("")

            return predictor, True

        except Exception as e:
            logger.error(f"Error entrenando modelos para {symbol}: {e}", exc_info=True)
            return None, False

    def process_symbol(self, symbol: str) -> bool:
        """
        Procesa un símbolo: verifica predicciones, entrena/carga modelos, genera predicciones.

        FLUJO:
        1. Verificar si ya hay predicciones para esta hora
        2. Si ya existen, saltar
        3. Si no existen:
           a. Obtener/entrenar modelos multi-horizonte
           b. Determinar ventana de predicción (últimos 2880 minutos)
           c. Generar predicciones para próximos 60 minutos
           d. Guardar en MongoDB

        Args:
            symbol: Símbolo de la moneda

        Returns:
            True si se procesó exitosamente (generó predicciones o ya existían)
        """
        try:
            logger.info("\n" + "="*80)
            logger.info(f"PROCESANDO SÍMBOLO: {symbol.upper()}")
            logger.info("="*80)

            # 1. Verificar si ya hay predicciones para esta hora
            if self.check_predictions_for_current_hour(symbol):
                logger.info(f"✓ {symbol} ya tiene predicciones para esta hora. Saltando...")
                return True

            # 2. Obtener o entrenar modelos
            logger.info(f"Obteniendo modelos para {symbol}...")
            predictor, is_new = self._get_or_train_models(symbol)

            if not predictor:
                logger.error(f"No se pudieron obtener modelos para {symbol}")
                return False

            if is_new:
                logger.info(f"✓ Modelos nuevos entrenados para {symbol}")
            else:
                logger.info(f"✓ Modelos existentes cargados para {symbol}")

            # 3. Determinar ventana de predicción (usar ventana MÁS GRANDE)
            logger.info(f"Obteniendo datos para predicción...")

            # Obtener todos los datos históricos
            all_data = self.mongo_client.get_all_historical_data(symbol)

            if not all_data:
                logger.error(f"No hay datos para predicción de {symbol}")
                return False

            # Usar la ventana más grande para tener datos suficientes para todos los horizontes
            max_window_size = max(config.HORIZON_TRAINING_WINDOWS.values())

            # Determinar ventana de predicción
            try:
                lower_bound, reference_time, window_data = self.data_processor.determine_training_window(
                    all_data,
                    max_window_size
                )
            except Exception as e:
                logger.error(f"Error determinando ventana de predicción: {e}", exc_info=True)
                return False

            logger.info(f"✓ Ventana de predicción determinada:")
            logger.info(f"  Reference time: {reference_time}")
            logger.info(f"  Datos: {len(window_data)} minutos ({max_window_size} max)")

            # 4. Generar predicciones para los próximos 60 minutos
            logger.info(f"Generando predicciones para {symbol}...")

            predictions = predictor.predict_next_60_minutes(
                window_data,
                reference_time,
                mongo_client=self.mongo_client,  # Pasar mongo_client para continuidad con datos reales
                symbol=symbol
            )

            if not predictions:
                logger.error(f"No se generaron predicciones para {symbol}")
                return False

            logger.info(f"✓ Predicciones generadas: {len(predictions)} minutos")

            # 5. Guardar predicciones en MongoDB
            logger.info(f"Guardando predicciones en MongoDB...")

            if not self.mongo_client.save_predictions(symbol, predictions):
                logger.error(f"Error guardando predicciones para {symbol}")
                return False

            logger.info(f"✓ Predicciones guardadas exitosamente")

            # Resumen
            first_pred = datetime.fromtimestamp(predictions[0]['open_time']/1000, tz=pytz.UTC)
            last_pred = datetime.fromtimestamp(predictions[-1]['open_time']/1000, tz=pytz.UTC)

            logger.info("\n" + "-"*80)
            logger.info(f"RESUMEN - {symbol.upper()}")
            logger.info("-"*80)
            logger.info(f"  Modelos: {'NUEVOS' if is_new else 'EXISTENTES'}")
            logger.info(f"  Predicciones: {len(predictions)}")
            logger.info(f"  Periodo: {first_pred} hasta {last_pred}")
            logger.info(f"  Horizontes cubiertos: {config.PREDICTION_HORIZONS}")
            logger.info("-"*80)

            logger.info(f"✓ {symbol.upper()} PROCESADO EXITOSAMENTE")
            logger.info("="*80)

            return True

        except Exception as e:
            logger.error(f"Error procesando {symbol}: {e}", exc_info=True)
            return False

    def process_all_symbols(self, symbols: List[str] = None) -> Dict:
        """
        Procesa todos los símbolos disponibles o una lista específica.

        Args:
            symbols: Lista de símbolos a procesar. Si None, procesa todos disponibles.

        Returns:
            Diccionario con estadísticas del proceso
        """
        try:
            # Determinar símbolos a procesar
            if symbols:
                symbols_to_process = symbols
            elif config.SYMBOLS_TO_PREDICT:
                symbols_to_process = config.SYMBOLS_TO_PREDICT
            else:
                symbols_to_process = self.mongo_client.get_available_symbols()

            if not symbols_to_process:
                logger.warning("No hay símbolos para procesar")
                return {'total': 0, 'success': 0, 'skipped': 0, 'failed': 0}

            logger.info("\n" + "="*80)
            logger.info("PROCESAMIENTO BATCH DE SÍMBOLOS")
            logger.info("="*80)
            logger.info(f"Símbolos a procesar: {symbols_to_process}")
            logger.info(f"Total: {len(symbols_to_process)}")
            logger.info("="*80)

            results = {
                'total': len(symbols_to_process),
                'success': 0,
                'skipped': 0,  # Ya tenían predicciones
                'failed': 0,
                'details': {}
            }

            for i, symbol in enumerate(symbols_to_process, 1):
                logger.info(f"\n[{i}/{len(symbols_to_process)}] Procesando {symbol}...")

                try:
                    # Verificar si ya tiene predicciones
                    if self.check_predictions_for_current_hour(symbol):
                        results['skipped'] += 1
                        results['details'][symbol] = 'skipped'
                        logger.info(f"⏭ {symbol} saltado (ya tiene predicciones)")
                        continue

                    # Procesar símbolo
                    success = self.process_symbol(symbol)

                    if success:
                        results['success'] += 1
                        results['details'][symbol] = 'success'
                    else:
                        results['failed'] += 1
                        results['details'][symbol] = 'failed'

                except Exception as e:
                    logger.error(f"Error procesando {symbol}: {e}", exc_info=True)
                    results['failed'] += 1
                    results['details'][symbol] = f'error: {str(e)}'

            # Resumen final
            logger.info("\n" + "="*80)
            logger.info("RESUMEN FINAL DEL BATCH")
            logger.info("="*80)
            logger.info(f"Total procesados: {results['total']}")
            logger.info(f"  ✓ Exitosos: {results['success']}")
            logger.info(f"  ⏭ Saltados: {results['skipped']}")
            logger.info(f"  ✗ Fallidos: {results['failed']}")
            logger.info("="*80)

            if results['details']:
                logger.info("\nDetalle por símbolo:")
                for symbol, status in results['details'].items():
                    logger.info(f"  {symbol}: {status}")

            return results

        except Exception as e:
            logger.error(f"Error procesando símbolos: {e}", exc_info=True)
            return {'total': 0, 'success': 0, 'skipped': 0, 'failed': 0}

    def process_all_symbols_continuous(self):
        """
        Bucle continuo que procesa todos los símbolos.

        ALGORITMO:
        1. Para cada símbolo:
           a. Detectar última hora predicha del día
           b. Determinar próxima hora a predecir
           c. Validar que existan datos reales hasta esa hora
           d. Predecir intervalo si es posible
        2. Repetir cada VALIDATION_INTERVAL_SECONDS segundos
        """
        logger.info("Iniciando bucle continuo de predicción...")

        # Determinar símbolos a procesar
        if config.SYMBOLS_TO_PREDICT:
            symbols = config.SYMBOLS_TO_PREDICT
        else:
            symbols = self.mongo_client.get_available_symbols()

        logger.info(f"Símbolos a procesar: {symbols}")

        cycle = 0

        while True:
            cycle += 1
            now = datetime.now(pytz.UTC)

            logger.info(f"\n{'='*80}")
            logger.info(f"CICLO #{cycle} - {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            logger.info(f"{'='*80}")

            processed_any = False

            for symbol in symbols:
                try:
                    logger.info(f">>> Procesando {symbol} en ciclo #{cycle}")

                    # LÓGICA SEGÚN CONDICIONES.TXT (Sección 7):
                    # 1. Validar última predicción del día de hoy
                    # 2. Si no hay predicciones desde las 00:00, empezar desde ahí
                    # 3. Predecir hora por hora desde 00:00 hasta hora_actual + 1
                    # 4. Esperar datos reales necesarios para cada hora

                    current_hour = now.hour
                    current_date = now.date()
                    logger.info(f"{symbol}: Hora actual: {current_hour}:00")

                    # Obtener la última hora con predicciones del día de hoy
                    last_predicted_hour = self.get_last_prediction_hour_today(symbol)

                    if last_predicted_hour is None:
                        # No hay predicciones hoy, empezar desde las 00:00
                        start_hour = 0
                        logger.info(f"{symbol}: Sin predicciones hoy. Empezando desde 00:00")
                    else:
                        # Hay predicciones, empezar desde la siguiente hora
                        start_hour = last_predicted_hour + 1
                        logger.info(f"{symbol}: Última hora predicha: {last_predicted_hour}:00. Continuando desde {start_hour}:00")

                    # Predecir hasta hora_actual + 1 (una hora adelante)
                    end_hour = current_hour + 1

                    hours_predicted = 0

                    # Predecir hora por hora desde start_hour hasta end_hour
                    for target_hour in range(start_hour, end_hour + 1):
                        # Ajustar si target_hour >= 24 (día siguiente)
                        if target_hour >= 24:
                            logger.info(f"{symbol}: Alcanzado final del día. Target hour {target_hour} >= 24")
                            break

                        # Verificar si ya existe predicción para esta hora
                        if self.mongo_client.check_predictions_for_hour(symbol, target_hour):
                            logger.info(f"{symbol}: Predicción para hora {target_hour}:00 ya existe, saltando...")
                            continue

                        # LÓGICA CORREGIDA: Para predecir la hora target_hour (ej: 22:00-23:00),
                        # necesitamos que EXISTA el dato REAL de las target_hour:00
                        # Ejemplo: Para predecir 22:00-23:00, necesitamos el dato REAL de las 22:00
                        if target_hour == 0:
                            # Para predecir 00:00-01:00, necesitamos datos del día anterior
                            # Por simplicidad, saltamos la hora 0 si no hay datos
                            logger.info(f"{symbol}: Saltando hora 0 (requiere datos del día anterior)")
                            continue

                        # IMPORTANTE: required_data_hour es la hora EXACTA cuyo dato necesitamos
                        required_data_hour = target_hour

                        # Verificar que exista el dato REAL de la hora target_hour:00
                        if not self.check_exact_hour_data_exists(symbol, required_data_hour):
                            logger.info(f"{symbol}: ⏳ Esperando dato REAL de hora {required_data_hour}:00 para predecir intervalo {target_hour}:00-{target_hour+1}:00...")
                            break  # Si no existe el dato, esperar al siguiente ciclo

                        # Predecir esta hora
                        logger.info(f"{symbol}: Prediciendo intervalo {target_hour}:00-{target_hour+1}:00 del día {current_date}...")
                        success = self.predict_hour_interval(symbol, target_hour)

                        if success:
                            hours_predicted += 1
                            processed_any = True
                            logger.info(f"✓ {symbol}: Hora {target_hour}:00-{target_hour+1}:00 completada (12 predicciones)")
                        else:
                            logger.error(f"✗ {symbol}: Error prediciendo hora {target_hour}")
                            break  # Si falla una hora, no intentar las siguientes

                    if hours_predicted > 0:
                        logger.info(f"✓ {symbol}: {hours_predicted} hora(s) del día {current_date} predicha(s)")
                    else:
                        logger.debug(f"{symbol}: Sin predicciones pendientes en este ciclo")

                    # LIMPIEZA DE MEMORIA DESPUÉS DE CADA SÍMBOLO
                    # Esto garantiza que las predicciones de diferentes símbolos sean independientes
                    # y no haya contaminación de estado/caché entre símbolos
                    logger.debug(f"{symbol}: Limpiando memoria después de procesar símbolo...")
                    try:
                        gc.collect()
                    except Exception as cleanup_error:
                        logger.warning(f"Error durante limpieza de memoria para {symbol}: {cleanup_error}")

                except Exception as e:
                    logger.error(f"Error procesando {symbol}: {e}", exc_info=True)

            # Resumen del ciclo
            if processed_any:
                logger.info(f"✓ Ciclo #{cycle}: Predicciones generadas")
            else:
                logger.debug(f"⏭ Ciclo #{cycle}: Sin predicciones pendientes")

            # Limpiar modelos cada 10 ciclos
            if cycle % 10 == 0:
                try:
                    self.cleanup_old_models_all_symbols()
                except Exception as e:
                    logger.error(f"Error limpiando modelos: {e}")

            # Esperar antes del próximo ciclo
            logger.debug(f"Esperando {config.VALIDATION_INTERVAL_SECONDS}s...")
            time.sleep(config.VALIDATION_INTERVAL_SECONDS)

    def cleanup_old_models_all_symbols(self):
        """Limpia modelos obsoletos para todos los símbolos."""
        try:
            symbols = self.mongo_client.get_available_symbols()

            logger.info(f"Limpiando modelos obsoletos para {len(symbols)} símbolos...")

            for symbol in symbols:
                try:
                    self.model_manager.cleanup_old_models(symbol)
                except Exception as e:
                    logger.error(f"Error limpiando modelos de {symbol}: {e}")

            logger.info("✓ Limpieza de modelos completada")

        except Exception as e:
            logger.error(f"Error en limpieza de modelos: {e}", exc_info=True)

    def close(self):
        """Cierra las conexiones del servicio."""
        self.mongo_client.close()
        logger.info("Servicio de predicción cerrado")
