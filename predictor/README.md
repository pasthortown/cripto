# Servicio de Predicción con LSTM

Servicio de predicción de precios de criptomonedas utilizando redes LSTM (Long Short-Term Memory).

## Características

- **Red LSTM configurable**: Arquitectura de red neuronal con múltiples capas LSTM
- **Gestión automática de modelos**: Creación, almacenamiento y eliminación automática de modelos obsoletos
- **Predicción por minuto**: Genera predicciones minuto a minuto para todo el día
- **Múltiples monedas**: Procesa múltiples criptomonedas en paralelo
- **Validación diaria**: Evalúa modelos con datos del día anterior

## Arquitectura

### Componentes Principales

1. **lstm_predictor.py**: Implementación de la red LSTM
   - Preparación de datos
   - Creación de secuencias temporales
   - Entrenamiento del modelo
   - Generación de predicciones

2. **model_manager.py**: Gestión de modelos
   - Verificación de validez de modelos
   - Guardado y carga de modelos
   - Limpieza de modelos obsoletos

3. **mongo_client.py**: Cliente de MongoDB
   - Conexión a la base de datos
   - Obtención de datos históricos
   - Almacenamiento de predicciones

4. **prediction_service.py**: Servicio principal
   - Orquestación del proceso completo
   - Procesamiento de múltiples símbolos
   - Gestión de errores

5. **main.py**: Punto de entrada
   - Ejecución periódica del servicio
   - Logging y monitoreo

## Flujo de Trabajo

### Proceso por Moneda

1. **Verificación**: Comprueba si ya existen predicciones para el día actual
2. **Validación de Modelo**: Verifica si existe un modelo válido (< 1 día de antigüedad)
3. **Entrenamiento** (si es necesario):
   - Datos de entrenamiento: Todos los datos hasta las 00:00 de ayer (excluyendo ayer y hoy)
   - Datos de validación: Todo el día de ayer
   - Métricas: MSE, MAE, RMSE por característica
4. **Predicción**: Genera predicciones minuto a minuto para todo el día actual
5. **Almacenamiento**: Guarda predicciones en colección `prediccion_{moneda}`
6. **Limpieza**: Elimina modelos obsoletos (> 1 día)

### Datos de Entrada

Cada registro incluye:
- `open_time`: Timestamp de apertura (ms)
- `open`: Precio de apertura
- `high`: Precio máximo
- `low`: Precio mínimo
- `close`: Precio de cierre
- `volume`: Volumen de operaciones

### Datos de Salida

Las predicciones se almacenan con:
- Todos los campos del registro original
- `predicted_at`: Timestamp de cuando se generó la predicción

## Configuración

### Variables de Entorno

```bash
# MongoDB
MONGODB_HOST=mongodb
MONGODB_PORT=27017
MONGODB_DATABASE=binance_data
MONGODB_USERNAME=admin
MONGODB_PASSWORD=SecurePass123!

# Modelo LSTM
LSTM_UNITS=128                  # Unidades por capa LSTM
LSTM_LAYERS=2                   # Número de capas LSTM
DROPOUT_RATE=0.2               # Tasa de dropout
EPOCHS=50                      # Épocas de entrenamiento
BATCH_SIZE=32                  # Tamaño de lote
SEQUENCE_LENGTH=60             # Minutos de historia (60 = 1 hora)

# Gestión de Modelos
MODELS_DIR=/app/models
MODEL_MAX_AGE_DAYS=1          # Antigüedad máxima del modelo (días)

# Ejecución
PREDICTION_INTERVAL_HOURS=24  # Intervalo entre ejecuciones (horas)
SYMBOLS_TO_PREDICT=           # Monedas específicas (vacío = todas)

# Logging
LOG_LEVEL=INFO
LOG_DIR=/logs
```

### Almacenamiento de Modelos

Los modelos se guardan en `/app/models/{moneda}/`:
- `model_YYYYMMDD.keras`: Modelo entrenado
- `scaler_YYYYMMDD.pkl`: Normalizador de datos
- `metadata_YYYYMMDD.pkl`: Métricas y configuración

## Colecciones de MongoDB

### Colecciones de Origen
- `btcusdt`, `ethusdt`, etc.: Datos históricos de klines

### Colecciones de Predicción
- `prediccion_btcusdt`, `prediccion_ethusdt`, etc.: Predicciones generadas

## Métricas de Evaluación

El modelo se evalúa con:
- **MSE** (Mean Squared Error): Error cuadrático medio
- **MAE** (Mean Absolute Error): Error absoluto medio
- **RMSE** (Root Mean Squared Error): Raíz del error cuadrático medio

Métricas calculadas para:
- Global (todas las características)
- Por característica (open, high, low, close, volume)

## Logs

Se generan dos archivos de log diarios:
- `predictor_YYYY-MM-DD.txt`: Log general
- `predictor_errors_YYYY-MM-DD.txt`: Solo errores

## Ejecución

El servicio se ejecuta automáticamente cada 24 horas:
1. Verifica predicciones existentes
2. Entrena o carga modelo
3. Genera predicciones para el día
4. Guarda en MongoDB
5. Espera hasta la próxima ejecución

## Notas Importantes

- **Datos insuficientes**: Se requieren al menos `SEQUENCE_LENGTH` registros para entrenar
- **Validación de modelos**: Los modelos se reentrenan diariamente para adaptarse a nuevos patrones
- **Predicciones existentes**: Si ya existen predicciones para el día, se omite el proceso
- **Gestión de memoria**: Los modelos obsoletos se eliminan automáticamente

## Tecnologías

- **TensorFlow/Keras**: Framework de deep learning
- **NumPy/Pandas**: Procesamiento de datos
- **scikit-learn**: Normalización y métricas
- **PyMongo**: Conexión a MongoDB
- **Python 3.11**: Lenguaje de programación
