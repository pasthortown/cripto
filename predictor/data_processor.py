"""
Procesador de datos para la nueva arquitectura multi-horizonte.

Responsabilidades:
1. Determinar ventana exacta de 2880 minutos usando algoritmo específico
2. Crear features con resampling multi-escala
3. Construir targets para cada horizonte mediante agregación de velas
4. Preparar datasets supervisados para entrenamiento
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pytz
from logger_config import setup_logger
import config

logger = setup_logger(__name__, config.LOG_DIR, config.LOG_LEVEL)


class DataProcessor:
    """Procesador de datos para estrategia multi-horizonte."""

    def __init__(self):
        """Inicializa el procesador de datos."""
        self.input_columns = config.INPUT_COLUMNS
        self.target_columns = config.TARGET_COLUMNS
        self.resample_windows = config.RESAMPLE_WINDOWS
        self.horizon_intervals = config.HORIZON_INTERVALS

    def determine_training_window(
        self,
        all_data: List[Dict],
        window_size: int
    ) -> Tuple[datetime, datetime, List[Dict]]:
        """
        Determina la ventana exacta de N minutos usando el algoritmo específico.

        ALGORITMO (según condiciones.txt):
        1. Identificar la última hora redonda en la base de datos
        2. Truncar eliminando minutos y segundos (hora redonda)
        3. Este es reference_time (límite superior exclusivo)
        4. Calcular lower_bound = reference_time - window_size minutos
        5. Obtener exactamente window_size datos en [lower_bound, reference_time)

        Args:
            all_data: Lista completa de datos históricos del símbolo
            window_size: Tamaño de ventana en minutos (2880, 4320, 5760, 8640)

        Returns:
            Tupla (lower_bound, reference_time, window_data)
            - lower_bound: Inicio de la ventana (inclusivo)
            - reference_time: Fin de la ventana (exclusivo)
            - window_data: Exactamente window_size registros de la ventana
        """
        if not all_data or len(all_data) == 0:
            raise ValueError("No hay datos disponibles para determinar la ventana de entrenamiento")

        # Convertir a DataFrame para facilitar el procesamiento
        df = pd.DataFrame(all_data)

        # 1. Identificar el máximo timestamp disponible
        max_timestamp = df['open_time'].max()
        max_datetime = datetime.fromtimestamp(max_timestamp / 1000, tz=pytz.UTC)

        logger.info(f"Máximo timestamp en datos: {max_datetime}")

        # 2. Truncar a hora redonda (eliminar minutos, segundos, microsegundos)
        reference_time = max_datetime.replace(minute=0, second=0, microsecond=0)

        logger.info(f"Reference time (hora redonda): {reference_time}")

        # 3. Calcular lower_bound restando window_size minutos
        lower_bound = reference_time - timedelta(minutes=window_size)

        logger.info(f"Lower bound: {lower_bound}")
        logger.info(f"Ventana de entrenamiento: [{lower_bound}, {reference_time}) = {window_size} minutos")

        # 4. Filtrar datos en la ventana [lower_bound, reference_time)
        lower_bound_ms = int(lower_bound.timestamp() * 1000)
        reference_time_ms = int(reference_time.timestamp() * 1000)

        # Filtrar: timestamp >= lower_bound y timestamp < reference_time
        window_df = df[(df['open_time'] >= lower_bound_ms) & (df['open_time'] < reference_time_ms)].copy()

        # Ordenar por timestamp
        window_df = window_df.sort_values('open_time').reset_index(drop=True)

        # 5. Validar que tengamos exactamente window_size registros
        actual_count = len(window_df)

        if actual_count < window_size:
            raise ValueError(
                f"Datos insuficientes en la ventana. "
                f"Se requieren {window_size} minutos, "
                f"pero solo hay {actual_count} disponibles"
            )

        # Si hay más de window_size, tomar los últimos window_size (más recientes)
        if actual_count > window_size:
            logger.warning(f"Hay {actual_count} registros en la ventana, tomando los últimos {window_size}")
            window_df = window_df.tail(window_size).reset_index(drop=True)

        window_data = window_df.to_dict('records')

        logger.info(f"✓ Ventana determinada:")
        logger.info(f"  - Lower bound: {lower_bound}")
        logger.info(f"  - Reference time: {reference_time}")
        logger.info(f"  - Registros en ventana: {len(window_data)}")
        logger.info(f"  - Primer registro: {datetime.fromtimestamp(window_data[0]['open_time']/1000, tz=pytz.UTC)}")
        logger.info(f"  - Último registro: {datetime.fromtimestamp(window_data[-1]['open_time']/1000, tz=pytz.UTC)}")

        return lower_bound, reference_time, window_data

    def create_resampled_features(self, window_data: List[Dict]) -> pd.DataFrame:
        """
        Crea features con resampling multi-escala.

        Para cada ventana N en RESAMPLE_WINDOWS:
        - Agrupa las velas de 1 minuto en bloques de N minutos
        - Genera agregados OHLCV para cada bloque
        - Agrega estas series como features adicionales

        Args:
            window_data: Lista de 2880 velas de 1 minuto

        Returns:
            DataFrame con features multi-escala
        """
        # Convertir a DataFrame
        df = pd.DataFrame(window_data)

        # Convertir columnas OHLCV a numérico
        for col in self.input_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Convertir open_time a datetime para resampling
        df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
        df = df.set_index('datetime')

        # DataFrame resultante con todas las features
        features_df = df[self.input_columns].copy()

        # Crear features resampleadas para cada ventana N
        for window_size in self.resample_windows:
            if window_size == 1:
                # Ventana de 1 minuto = datos originales, ya están incluidos
                continue

            logger.info(f"Creando features resampleadas para ventana de {window_size} minutos...")

            # Resamplear a ventana de N minutos
            resampled = df[self.input_columns].resample(f'{window_size}T').agg({
                'open': 'first',   # Primer valor del intervalo
                'high': 'max',     # Máximo del intervalo
                'low': 'min',      # Mínimo del intervalo
                'close': 'last',   # Último valor del intervalo
                'volume': 'sum'    # Suma de volúmenes
            })

            # Forward fill para alinear con los datos de 1 minuto
            # Cada valor resampleado se propaga hacia adelante hasta el próximo valor
            resampled_filled = resampled.reindex(df.index, method='ffill')

            # Agregar como nuevas columnas con sufijo
            for col in self.input_columns:
                feature_name = f"{col}_resample_{window_size}m"
                features_df[feature_name] = resampled_filled[col]

        # Rellenar NaN (bfill luego ffill)
        features_df = features_df.bfill().ffill()

        logger.info(f"✓ Features creadas: {len(features_df.columns)} columnas")
        logger.info(f"  - Columnas base: {self.input_columns}")
        logger.info(f"  - Features resampleadas: {len(features_df.columns) - len(self.input_columns)}")

        return features_df

    def create_target_for_horizon(
        self,
        window_data: List[Dict],
        reference_time: datetime,
        horizon: int
    ) -> pd.Series:
        """
        Crea el target para un horizonte específico mediante VARIACIONES (deltas).

        NUEVA ESTRATEGIA:
        En lugar de predecir valores absolutos OHLCV, predecimos VARIACIONES:
        - close_delta: cambio en precio de cierre (close_futuro - close_anterior)
        - high_delta: diferencia entre high futuro y close anterior
        - low_delta: diferencia entre low futuro y close anterior
        - volume: volumen total (valor directo)

        Para cada punto de corte histórico t_i:
        1. Obtener close anterior (close en t_i)
        2. Definir el intervalo futuro según HORIZON_INTERVALS[horizon]
        3. Agregar las velas de 1 minuto en ese intervalo
        4. Calcular variaciones respecto al close anterior

        Args:
            window_data: Lista de 2880 velas de 1 minuto
            reference_time: Tiempo de referencia (hora redonda)
            horizon: Horizonte temporal (ej: 1, 2, 5, 10, etc.)

        Returns:
            DataFrame con los targets (variaciones) para este horizonte
        """
        # Obtener intervalo del horizonte
        interval_start, interval_end = self.horizon_intervals[horizon]

        # Convertir a DataFrame
        df = pd.DataFrame(window_data)

        # Convertir columnas a numérico
        for col in self.input_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')

        # Lista para almacenar targets
        targets = []

        # Para cada punto de corte t_i en la ventana
        # Necesitamos que haya al menos 'interval_end' minutos futuros disponibles
        max_cutoff_index = len(df) - interval_end

        for i in range(max_cutoff_index):
            # Punto de corte t_i
            cutoff_time = df.iloc[i]['datetime']

            # Obtener close anterior (precio de cierre en el punto de corte)
            prev_close = df.iloc[i]['close']

            # Definir intervalo futuro relativo a t_i
            # [t_i + interval_start, t_i + interval_end)
            future_start = cutoff_time + timedelta(minutes=interval_start)
            future_end = cutoff_time + timedelta(minutes=interval_end)

            # Obtener velas en el intervalo futuro
            future_candles = df[
                (df['datetime'] >= future_start) &
                (df['datetime'] < future_end)
            ]

            if len(future_candles) == 0:
                # No hay datos futuros suficientes para este punto de corte
                continue

            # Agregar velas del intervalo para obtener valores futuros
            future_high = future_candles['high'].max()
            future_low = future_candles['low'].min()
            future_close = future_candles.iloc[-1]['close']
            future_volume = future_candles['volume'].sum()

            # Calcular VARIACIONES respecto al close anterior
            aggregated_target = {
                'close_delta': future_close - prev_close,   # Cambio en el precio de cierre
                'high_delta': future_high - prev_close,     # Diferencia entre high y close anterior
                'low_delta': future_low - prev_close,       # Diferencia entre low y close anterior
                'volume': future_volume                     # Volumen total (valor directo)
            }

            targets.append(aggregated_target)

        # Convertir a DataFrame
        targets_df = pd.DataFrame(targets)

        logger.info(f"✓ Targets (variaciones) creados para horizonte {horizon} minutos:")
        logger.info(f"  - Intervalo: [{interval_start}, {interval_end}) minutos")
        logger.info(f"  - Número de samples: {len(targets_df)}")
        logger.info(f"  - Columnas: {list(targets_df.columns)}")

        return targets_df

    def create_supervised_dataset(
        self,
        window_data: List[Dict],
        reference_time: datetime,
        horizon: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Crea dataset supervisado (X, y) para un horizonte específico.

        X: Features (base + resampleadas)
        y: Targets (velas agregadas del horizonte)

        Args:
            window_data: Lista de 2880 velas de 1 minuto
            reference_time: Tiempo de referencia
            horizon: Horizonte temporal

        Returns:
            Tupla (X, y) con arrays de numpy
        """
        logger.info(f"Creando dataset supervisado para horizonte {horizon} minutos...")

        # 1. Crear features con resampling
        features_df = self.create_resampled_features(window_data)

        # 2. Crear targets para el horizonte
        targets_df = self.create_target_for_horizon(window_data, reference_time, horizon)

        # 3. Alinear features y targets
        # Los targets empiezan desde el índice 0 pero corresponden a las features
        # desde el índice 0 hasta max_cutoff_index
        interval_start, interval_end = self.horizon_intervals[horizon]
        max_samples = len(targets_df)

        # Tomar features correspondientes (primeras max_samples filas)
        X = features_df.iloc[:max_samples].values
        y = targets_df.values

        logger.info(f"✓ Dataset supervisado creado:")
        logger.info(f"  - X shape: {X.shape} (samples, features)")
        logger.info(f"  - y shape: {y.shape} (samples, targets)")

        return X, y

    def prepare_prediction_features(self, recent_data: List[Dict], window_size: int = None) -> np.ndarray:
        """
        Prepara features para predicción a partir de datos recientes.

        Args:
            recent_data: Datos históricos recientes
            window_size: Tamaño de ventana en minutos (si None, usa max de HORIZON_TRAINING_WINDOWS)

        Returns:
            Array de features para predicción (1, n_features)
        """
        # Si no se especifica, usar la ventana más grande
        if window_size is None:
            window_size = max(config.HORIZON_TRAINING_WINDOWS.values())

        if len(recent_data) < window_size:
            raise ValueError(
                f"Datos insuficientes para predicción. "
                f"Se requieren {window_size} minutos, "
                f"pero solo hay {len(recent_data)}"
            )

        # Tomar los últimos window_size minutos
        window_data = recent_data[-window_size:]

        # Crear features con resampling
        features_df = self.create_resampled_features(window_data)

        # Tomar la última fila (estado más reciente)
        prediction_features = features_df.iloc[-1:].values

        logger.info(f"✓ Features de predicción preparadas: {prediction_features.shape}")

        return prediction_features
