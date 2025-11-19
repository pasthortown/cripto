# Changelog - Binance Crypto Predictor

Historial de cambios importantes del sistema de predicción y análisis de criptomonedas.

---

## [2.0] - 2025-11-18

### Predictor Multi-Horizonte - Versión 2.0

**Cambios Mayores:**

#### Ventanas de Datos Variables por Horizonte

- **Agregado**: `HORIZON_TRAINING_WINDOWS` en `config.py`
  - Horizontes cortos (1-6 min): 2880 minutos (2 días)
  - Horizontes medios (10-15 min): 4320 minutos (3 días)
  - Horizontes largos (20-30 min): 5760 minutos (4 días)
  - Horizontes muy largos (60 min): 8640 minutos (6 días)

- **Modificado**: `data_processor.py::determine_training_window()`
  - Ahora acepta parámetro `window_size` para ventanas dinámicas
  - Cada horizonte usa su propia ventana de datos específica

- **Modificado**: `data_processor.py::prepare_prediction_features()`
  - Parámetro opcional `window_size`
  - Si no se especifica, usa la ventana más grande (8640 min)

#### Entrenamiento con Ventanas Variables

- **Reescrito**: `lstm_predictor.py::train_models_for_all_horizons()`
  - Recibe `symbol` y `all_data` en lugar de `window_data` fija
  - Para cada horizonte:
    1. Obtiene su ventana específica
    2. Crea dataset con esa ventana
    3. Entrena modelo
  - Logs mejorados con información de ventana por horizonte

#### Bucle Continuo y Recuperación

- **Agregado**: `prediction_service.py::process_all_symbols_continuous()`
  - Bucle infinito que valida cada 5 segundos
  - Detecta última hora predicha del día
  - Completa horas faltantes secuencialmente
  - Espera datos reales antes de predecir
  - Validación continua

- **Actualizado**: `prediction_service.py::_train_new_models()`
  - Pasa `symbol` y `all_data` al entrenamiento
  - En lugar de `window_data` predeterminada

- **Actualizado**: `prediction_service.py::predict_hour_interval()`
  - Usa ventana MÁS GRANDE para predicción (8640 min)

#### Validación y Verificación

- **Agregado**: `mongo_client.py::check_predictions_for_hour()`
  - Verifica si ya existen predicciones para una hora específica
  - Evita duplicados

- **Existente**: `mongo_client.py::get_last_prediction_hour_today()`
  - Detecta última predicción del día

- **Existente**: `mongo_client.py::check_real_data_available_until()`
  - Valida disponibilidad de datos reales

#### Simplificación de main.py

- **Simplificado**: `main.py`
  - Delega toda la lógica de bucle al servicio
  - Llama a `service.process_all_symbols_continuous()`

**Mejoras:**

- Predicciones más precisas con ventanas optimizadas por horizonte
- Recuperación automática ante caídas del servicio
- Continuidad garantizada: open(n) = close(n-1) REAL
- Predicción con variaciones (deltas) en lugar de valores absolutos
- Intervalos sin solapamiento que cubren exactamente 60 minutos

**Métricas Esperadas:**

- Horizontes 1-6 min: val_loss ~0.003-0.005
- Horizontes 10-15 min: val_loss ~0.005-0.008
- Horizontes 20-30 min: val_loss ~0.008-0.012
- Horizonte 60 min: val_loss ~0.012-0.020

---

## [1.5] - 2025-11-18

### Ciclo de Vida de Modelos - Vigencia Diaria

**Cambios Mayores:**

#### Configuración

- **Agregado**: `config.py::MODEL_VALIDITY_MODE`
  - Valor: "daily" (los modelos son válidos todo el día)
  - Alternativa: "hourly" (para testing)

- **Actualizado**: `config.py::MODEL_MAX_AGE_HOURS`
  - Solo se usa en modo "hourly"
  - Valor por defecto: 24 horas

#### Gestión de Modelos

- **Modificado**: `model_manager.py::_get_model_file_paths()`
  - **ANTES**: Formato con hora `model_btcusdt_horizon1_20251118_13.keras`
  - **AHORA**: Formato solo con fecha `model_btcusdt_horizon1_20251118.keras`

- **Reescrito**: `model_manager.py::check_models_validity()`
  - Validación estricta por DÍA (no por horas)
  - Compara `model_date.date() == today`
  - Los modelos son válidos solo si fueron creados el día actual

- **Modificado**: `model_manager.py::save_models()`
  - Guarda con formato diario: `YYYYMMDD`
  - Sin incluir hora en el nombre del archivo

- **Reescrito**: `model_manager.py::cleanup_old_models()`
  - Elimina modelos que NO sean del día actual
  - Comparación simple de fechas
  - Se ejecuta automáticamente antes de entrenar

#### Servicio de Predicción

- **Actualizado**: `prediction_service.py::_get_or_train_models()`
  - Logs claros distinguiendo ENTRENAR vs CARGAR
  - Mensajes informativos sobre tiempo estimado
  - Limpieza automática de modelos viejos antes de entrenar

- **Mejorado**: `prediction_service.py::_train_new_models()`
  - Logs estructurados con prefijo `[symbol]`
  - Muestra métricas (val_loss) de cada horizonte
  - Formato consistente y legible

**Mejoras:**

**Eficiencia:**
- Ahorro de ~114 minutos/día por símbolo
- 1 entrenamiento/día en lugar de 24
- Carga rápida de modelos (~2 segundos)

**Consistencia:**
- Mismos modelos todo el día
- Predicciones comparables
- Métricas estables

**Gestión de Recursos:**
- ~12 archivos por símbolo en lugar de ~288/día
- Limpieza automática al cambio de día
- Recuperación rápida tras caídas

**Timeline Típico:**
```
00:00 → ENTRENAR (~5 min) + Predecir
01:00 → CARGAR (~2 seg) + Predecir
02:00 → CARGAR (~2 seg) + Predecir
...
23:00 → CARGAR (~2 seg) + Predecir
```

---

## [1.0] - 2025-11-10

### Sistema Inicial - Predictor Multi-Horizonte

**Componentes Principales:**

#### Backend API (Tornado)
- 7 endpoints REST: Health, Sync, Data, Stats, Predictions, Symbols
- WebSocket en `/ws/updates` para notificaciones en tiempo real
- Driver asíncrono Motor para MongoDB
- Sistema de suscripciones por símbolo

#### Coin Sync (Sincronización Automática)
- Sincronización cada 60 segundos desde Binance API
- Sincronización incremental (solo datos faltantes)
- Notificación a clientes WebSocket

#### Predictor LSTM
- 12 modelos especializados por horizonte temporal
- Arquitectura Bi-LSTM con Batch Normalization
- Horizontes: [1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60] minutos
- Ventana fija de 2880 minutos (48 horas)
- Ejecución cada hora en punto

#### Frontend Web
- Chart interactivo con Chart.js
- Actualización automática vía WebSocket
- Selector de monedas y rangos de tiempo
- Responsive design

#### MongoDB
- Colecciones: `klines_{symbol}` (datos reales)
- Colecciones: `prediccion_{symbol}` (predicciones)
- Indexación optimizada por timestamp

**Tecnologías:**

- Python 3.11
- Tornado 6.4.1 (API asíncrona)
- TensorFlow/Keras 2.15.0 (LSTM)
- MongoDB 7.0
- Docker y Docker Compose
- Nginx 1.25 (frontend)
- Chart.js 4.4

**Monedas Soportadas:**
- BTCUSDT (Bitcoin)
- ETHUSDT (Ethereum)
- BNBUSDT (Binance Coin)

**Métricas Iniciales:**
- R² Score: ~0.95
- MAPE: <3%
- Latencia WebSocket: <100ms
- Throughput Backend: ~1000 req/s

---

## [0.5] - 2025-06-01

### Fase Beta - Prototipo Inicial

**Componentes Básicos:**

- Sistema de recolección de datos históricos
- Almacenamiento en MongoDB sin optimización
- Modelo LSTM simple (horizonte único)
- API REST básica sin WebSocket
- Frontend estático sin actualizaciones en tiempo real

**Limitaciones:**
- Un solo horizonte de predicción (60 min)
- Sin sincronización automática
- Sin sistema de recuperación
- Entrenamiento manual

---

## Formato del Changelog

Este changelog sigue los principios de [Keep a Changelog](https://keepachangelog.com/en/1.0.0/):

- **Added**: Nuevas funcionalidades
- **Changed**: Cambios en funcionalidades existentes
- **Deprecated**: Funcionalidades obsoletas (próximas a eliminar)
- **Removed**: Funcionalidades eliminadas
- **Fixed**: Corrección de bugs
- **Security**: Cambios relacionados con seguridad

## Versionado

El proyecto sigue [Semantic Versioning](https://semver.org/):

- **MAJOR**: Cambios incompatibles en la API
- **MINOR**: Nuevas funcionalidades retrocompatibles
- **PATCH**: Correcciones de bugs retrocompatibles

---

**Última actualización**: 2025-11-18
