"""
Configuración del servicio de predicción con LSTM - NUEVA ARQUITECTURA.

Estrategia multi-horizonte:
- Ventana exacta de 2880 minutos (48 horas) determinada por algoritmo específico
- Modelos independientes para cada horizonte temporal
- Predicciones sin solapamiento (partición exacta del futuro)
- Features con resampling multi-escala
- Ejecución cada hora
"""

import os

# ============================================================================
# CONFIGURACIÓN DE MONGODB
# ============================================================================
MONGODB_HOST = os.getenv("MONGODB_HOST", "mongodb")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "binance_data")
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME", "admin")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "SecurePass123!")

# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "/logs")

# ============================================================================
# CONFIGURACIÓN DE MODELOS
# ============================================================================
MODELS_DIR = os.getenv("MODELS_DIR", "/app/models")

# VIGENCIA DE MODELOS (Sección 8: condiciones.txt)
# Los modelos se entrenan UNA VEZ al día (a las 00:00) y son válidos TODO el día
MODEL_VALIDITY_MODE = os.getenv("MODEL_VALIDITY_MODE", "daily")  # "daily" o "hourly" (para testing)
MODEL_MAX_AGE_HOURS = int(os.getenv("MODEL_MAX_AGE_HOURS", "24"))  # Solo para modo "hourly"

# ============================================================================
# VENTANA DE DATOS (VARIABLE POR HORIZONTE)
# ============================================================================
# TRAINING_WINDOW varía según el horizonte temporal:
# - Horizontes cortos (1-6 min) usan más datos recientes (2 días)
# - Horizontes medios (10-15 min) usan datos intermedios (3 días)
# - Horizontes largos (20-30 min) usan más historia (4 días)
# - Horizontes muy largos (60 min) usan máxima historia (6 días)

HORIZON_TRAINING_WINDOWS = {
    1:  2880,   # 2 días = 2880 minutos
    2:  2880,   # 2 días
    3:  2880,   # 2 días
    4:  2880,   # 2 días
    5:  2880,   # 2 días
    6:  2880,   # 2 días
    10: 4320,   # 3 días = 4320 minutos
    12: 4320,   # 3 días
    15: 4320,   # 3 días
    20: 5760,   # 4 días = 5760 minutos
    30: 5760,   # 4 días
    60: 8640    # 6 días = 8640 minutos
}

# ============================================================================
# HORIZONTES DE PREDICCIÓN
# ============================================================================
# Horizontes temporales en minutos: [1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60]
# Cada horizonte tiene su propio modelo y predice un intervalo específico sin solapamiento
PREDICTION_HORIZONS = [1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60]

# Mapeo de horizontes a intervalos (en minutos desde reference_time):
# Horizonte N → intervalo [inicio, fin)
# Estos intervalos NO se solapan y cubren los próximos 60 minutos
HORIZON_INTERVALS = {
    1:  (0, 1),    # [0, 1) minutos
    2:  (1, 2),    # [1, 2) minutos
    3:  (2, 3),    # [2, 3) minutos
    4:  (3, 4),    # [3, 4) minutos
    5:  (4, 5),    # [4, 5) minutos
    6:  (5, 6),    # [5, 6) minutos
    10: (6, 10),   # [6, 10) minutos
    12: (10, 12),  # [10, 12) minutos
    15: (12, 15),  # [12, 15) minutos
    20: (15, 20),  # [15, 20) minutos
    30: (20, 30),  # [20, 30) minutos
    60: (30, 60)   # [30, 60) minutos
}

# ============================================================================
# RESAMPLING DE FEATURES
# ============================================================================
# Tamaños de ventana para resampling de features (en minutos)
# Se crean series agregadas para cada uno de estos tamaños
RESAMPLE_WINDOWS = [1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60]

# ============================================================================
# CONFIGURACIÓN DE LA RED LSTM
# ============================================================================
# Arquitectura de la red neuronal
LSTM_UNITS = int(os.getenv("LSTM_UNITS", "128"))       # Unidades en cada capa LSTM
LSTM_LAYERS = int(os.getenv("LSTM_LAYERS", "2"))       # Número de capas LSTM
DROPOUT_RATE = float(os.getenv("DROPOUT_RATE", "0.2")) # Dropout para regularización

# Hiperparámetros de entrenamiento
EPOCHS = int(os.getenv("EPOCHS", "50"))                # Épocas máximas de entrenamiento
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "32"))        # Tamaño del batch
VALIDATION_SPLIT = float(os.getenv("VALIDATION_SPLIT", "0.2"))  # 20% para validación

# Learning rate
LEARNING_RATE = float(os.getenv("LEARNING_RATE", "0.001"))

# ============================================================================
# CONFIGURACIÓN DE EJECUCIÓN
# ============================================================================
# Intervalo de predicción: cada hora
PREDICTION_INTERVAL_HOURS = int(os.getenv("PREDICTION_INTERVAL_HOURS", "1"))

# Intervalo de validación: cada 5 segundos (bucle continuo)
VALIDATION_INTERVAL_SECONDS = int(os.getenv("VALIDATION_INTERVAL_SECONDS", "5"))

# Lista de símbolos a procesar (vacío = todos los disponibles en BD)
SYMBOLS_TO_PREDICT = os.getenv("SYMBOLS_TO_PREDICT", "").split(",") if os.getenv("SYMBOLS_TO_PREDICT") else []

# ============================================================================
# VARIABLES DE PREDICCIÓN
# ============================================================================
# Columnas input base (OHLCV)
INPUT_COLUMNS = ['open', 'high', 'low', 'close', 'volume']

# Columnas target (variables que se predicen mediante variaciones/deltas)
# Para cada horizonte, se predicen VARIACIONES respecto al close anterior:
# - close_delta: cambio en el precio de cierre
# - high_delta: diferencia entre high y close anterior
# - low_delta: diferencia entre low y close anterior
# - volume: volumen total (puede ser valor directo o delta según implementación)
TARGET_COLUMNS = ['close_delta', 'high_delta', 'low_delta', 'volume']

# ============================================================================
# VALIDACIONES
# ============================================================================
# Validar que los horizontes estén ordenados
assert PREDICTION_HORIZONS == sorted(PREDICTION_HORIZONS), \
    "PREDICTION_HORIZONS debe estar ordenado de menor a mayor"

# Validar que los intervalos cubran exactamente 60 minutos sin solapamientos
last_end = 0
for horizon in PREDICTION_HORIZONS:
    start, end = HORIZON_INTERVALS[horizon]
    assert start == last_end, \
        f"Intervalo del horizonte {horizon} no es consecutivo: [{start}, {end}) debe empezar en {last_end}"
    last_end = end
assert last_end == 60, \
    f"Los intervalos deben cubrir exactamente 60 minutos, pero cubren {last_end}"

# Validar que RESAMPLE_WINDOWS esté ordenado
assert RESAMPLE_WINDOWS == sorted(RESAMPLE_WINDOWS), \
    "RESAMPLE_WINDOWS debe estar ordenado de menor a mayor"

# Validar que todos los horizontes tengan ventana definida
for horizon in PREDICTION_HORIZONS:
    assert horizon in HORIZON_TRAINING_WINDOWS, \
        f"Horizonte {horizon} no tiene ventana de entrenamiento definida en HORIZON_TRAINING_WINDOWS"

print("✓ Configuración validada correctamente")
print(f"  - Horizontes de predicción: {PREDICTION_HORIZONS}")
print(f"  - Ventanas de entrenamiento variables:")
for h, w in HORIZON_TRAINING_WINDOWS.items():
    print(f"    Horizonte {h:2d} min → {w:4d} min ({w/1440:.1f} días)")
print(f"  - Ventanas de resampling: {RESAMPLE_WINDOWS}")
print(f"  - Modelos LSTM: {LSTM_LAYERS} capas x {LSTM_UNITS} unidades")
print(f"  - Intervalo de validación: {VALIDATION_INTERVAL_SECONDS} segundos")
