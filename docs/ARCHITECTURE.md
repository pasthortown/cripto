# Arquitectura del Sistema - Binance Crypto Predictor

**Documento técnico completo de la arquitectura del sistema**

Versión: 2.0
Fecha: Noviembre 2025

---

## Tabla de Contenidos

1. [Visión General](#visión-general)
2. [Arquitectura de Alto Nivel](#arquitectura-de-alto-nivel)
3. [Componentes Detallados](#componentes-detallados)
4. [Flujo de Datos](#flujo-de-datos)
5. [Base de Datos](#base-de-datos)
6. [Red Docker](#red-docker)
7. [Comunicaciones](#comunicaciones)
8. [Escalabilidad](#escalabilidad)

---

## Visión General

Sistema distribuido basado en microservicios Dockerizados para análisis y predicción de criptomonedas en tiempo real.

### Principios de Diseño

- **Asincronía**: Operaciones I/O no bloqueantes (Tornado, Motor, aiohttp)
- **Desacoplamiento**: Servicios independientes comunicados vía APIs
- **Persistencia**: Volúmenes Docker para datos y modelos
- **Escalabilidad**: Arquitectura preparada para escalar horizontalmente
- **Observabilidad**: Logging estructurado y rotativo

---

## Arquitectura de Alto Nivel

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           VISTA COMPLETA DEL SISTEMA                     │
└──────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────┐
                              │   Binance    │
                              │     API      │
                              │  (Público)   │
                              └───────┬──────┘
                                      │
                                      │ HTTPS REST
                                      │ (klines 1m)
                                      ▼
        ┌──────────────────────────────────────────────────────────────────┐
        │              Docker Network: cripto_net                          │
        │              192.168.31.0/24                                     │
        └──────────────────────────────────────────────────────────────────┘

┌────────────────┐    ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│   Coin Sync    │    │    Backend     │    │   Predictor    │    │   Frontend     │
│  192.168.31.12 │───►│ 192.168.31.11  │    │ 192.168.31.13  │    │ 192.168.31.14  │
│                │    │                │    │                │    │                │
│ Python 3.11    │    │ Tornado 6.4.1  │    │ TensorFlow 2.15│    │ Nginx 1.25     │
│ Requests       │    │ Motor (async)  │    │ Bi-LSTM x12    │    │ Chart.js 4.4   │
│                │    │ WebSocket      │    │ Multi-Horizonte│    │ JavaScript     │
│ Intervalo: 60s │    │ 7 Endpoints    │    │ Intervalo: 1h  │    │ Puerto: 8080   │
└────────────────┘    └────────┬───────┘    └────────┬───────┘    └────────┬───────┘
                               │                     │                     │
                               │ Motor (async)       │ PyMongo            │ HTTP/WS
                               ├─────────────────────┴─────────────────────┤
                               │                                           │
                      ┌────────▼───────────────────────────────────────────▼────┐
                      │                  MongoDB 7.0                            │
                      │               192.168.31.10:27017                       │
                      │              Puerto externo: 21018                      │
                      │                                                         │
                      │  Database: binance_data                                 │
                      │  ├─ klines_btcusdt        (datos reales)                │
                      │  ├─ klines_ethusdt        (datos reales)                │
                      │  ├─ klines_bnbusdt        (datos reales)                │
                      │  ├─ prediccion_btcusdt    (predicciones)                │
                      │  ├─ prediccion_ethusdt    (predicciones)                │
                      │  └─ prediccion_bnbusdt    (predicciones)                │
                      │                                                         │
                      │  Autenticación: admin / SecurePass123!                  │
                      │                                                         │
                      │  Volúmenes persistentes:                                │
                      │  ├─ mongodb_data         (/data/db)                     │
                      │  ├─ mongodb_config       (/data/configdb)               │
                      │  └─ predictor_models     (/app/models)                  │
                      └─────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────────────────────┐
        │              Volumen Compartido: ./logs                          │
        │              (Backend, Coin Sync, Predictor)                     │
        └──────────────────────────────────────────────────────────────────┘
```

---

## Componentes Detallados

### 1. MongoDB (Base de Datos)

**Propósito**: Almacenamiento persistente de datos históricos y predicciones

**Especificaciones**:
- **Imagen**: mongo:7.0
- **Container**: binance_mongodb
- **IP**: 192.168.31.10
- **Puerto Interno**: 27017
- **Puerto Externo**: 21018
- **Autenticación**: Obligatoria

**Características**:
- **Autenticación**: Usuario/contraseña con authSource=admin
- **Persistencia**: 2 volúmenes (data + config)
- **Health Check**: Ping cada 10s con mongosh
- **Restart Policy**: unless-stopped

**Estructura de Datos**:

```javascript
// Colección: klines_{symbol}
{
  "_id": ObjectId("..."),
  "open_time": 1731628800000,     // Único (índice)
  "open": "100000.50",
  "high": "100500.00",
  "low": "99800.00",
  "close": "100200.00",
  "volume": "1500.25",
  "close_time": 1731628859999,
  "quote_asset_volume": "...",
  "number_of_trades": 1234,
  "taker_buy_base_asset_volume": "...",
  "taker_buy_quote_asset_volume": "...",
  "timestamp": ISODate("2025-11-17T14:00:00Z")
}

// Colección: prediccion_{symbol}
{
  "_id": ObjectId("..."),
  "open_time": 1731628800000,     // Único (índice)
  "open": "100150.25",
  "high": "100450.30",
  "low": "99900.50",
  "close": "100250.75",
  "volume": "1480.50",
  "close_time": 1731628859999,
  "predicted_at": "2025-11-17T13:00:01Z",
  "model_version": "Bi-LSTM",
  "minutes_ahead": 5              // Horizonte de predicción
}
```

---

### 2. Backend (Tornado API)

**Propósito**: API REST y WebSocket para consulta de datos y notificaciones en tiempo real

**Especificaciones**:
- **Framework**: Tornado 6.4.1 (asíncrono)
- **Lenguaje**: Python 3.11
- **Container**: binance_backend
- **IP**: 192.168.31.11
- **Puerto**: 8888
- **Health Check**: HTTP GET /health cada 30s

**Arquitectura Interna**:

```
backend/
├── app/
│   ├── main.py                    # Servidor Tornado, rutas
│   ├── handlers.py                # Request handlers REST
│   ├── websocket_handler.py       # Handler WebSocket
│   ├── websocket_manager.py       # Gestor de conexiones WS
│   ├── binance_client.py          # Cliente Binance API
│   ├── db_client.py               # Cliente MongoDB (Motor)
│   ├── config.py                  # Variables de entorno
│   └── logger_config.py           # Sistema de logging
```

**Endpoints REST**:

| Método | Endpoint | Handler | Descripción |
|--------|----------|---------|-------------|
| GET | `/health` | HealthHandler | Health check del servicio |
| GET | `/api/symbols` | SymbolsHandler | Lista de monedas disponibles |
| POST | `/api/sync` | SyncDataHandler | Sincronizar datos de una moneda |
| GET | `/api/data/{symbol}` | GetDataHandler | Obtener datos históricos |
| GET | `/api/stats/{symbol}` | StatsHandler | Estadísticas de una moneda |
| GET | `/api/predictions/{symbol}` | PredictionsHandler | Obtener predicciones |

**WebSocket**:
- **URL**: `ws://localhost:8888/ws/updates`
- **Funcionalidad**: Notificaciones push cuando hay nuevos datos
- **Sistema de suscripciones**: Por símbolo

**Tecnologías Clave**:
- **Tornado**: Servidor web asíncrono (~10k conexiones concurrentes)
- **Motor**: Driver MongoDB asíncrono para asyncio
- **aiohttp**: Cliente HTTP asíncrono para Binance API
- **asyncio**: Event loop para operaciones no bloqueantes

---

### 3. Coin Sync (Sincronización Automática)

**Propósito**: Sincronizar datos de Binance cada 60 segundos automáticamente

**Especificaciones**:
- **Lenguaje**: Python 3.11
- **Container**: binance_coin_sync
- **IP**: 192.168.31.12
- **Intervalo**: 60 segundos (configurable)
- **Restart Policy**: unless-stopped

**Flujo de Trabajo**:

```
1. STARTUP
   └─► Espera a que backend esté disponible (health check)
   └─► GET /api/symbols (obtener lista de monedas)
   └─► Sincronización inicial de todas las monedas

2. LOOP INFINITO (cada 60s)
   ├─► Health check del backend
   ├─► Para cada símbolo en la lista:
   │   ├─► POST /api/sync {"symbol": "BTCUSDT"}
   │   ├─► Log resultado (nuevos registros, precio)
   │   └─► Reintenta 3 veces si falla
   └─► Sleep 60 segundos

3. BACKEND RESPONSE (automático)
   └─► Notifica a clientes WebSocket suscritos
       {
         "type": "sync_complete",
         "symbol": "BTCUSDT",
         "statistics": {...}
       }
```

**Arquitectura Interna**:

```
coin_sync/
├── main.py               # Punto de entrada, scheduler
├── sync_service.py       # Lógica de sincronización
├── backend_client.py     # Cliente HTTP para backend
├── config.py             # Variables de entorno
└── logger_config.py      # Sistema de logging
```

---

### 4. Predictor (LSTM Multi-Horizonte)

**Propósito**: Generar predicciones de precios usando redes neuronales Bi-LSTM

**Especificaciones**:
- **Framework ML**: TensorFlow 2.15.0, Keras
- **Container**: binance_predictor
- **IP**: 192.168.31.13
- **Intervalo**: Cada hora en punto (ej: 13:00, 14:00)
- **Restart Policy**: always

**Estrategia Multi-Horizonte**:

```
12 MODELOS ESPECIALIZADOS POR SÍMBOLO
├─► Modelo 1:  Predice a 5 minutos   (ventana: 90 min)
├─► Modelo 2:  Predice a 10 minutos  (ventana: 180 min)
├─► Modelo 3:  Predice a 15 minutos  (ventana: 270 min)
├─► Modelo 4:  Predice a 20 minutos  (ventana: 360 min)
├─► Modelo 5:  Predice a 25 minutos  (ventana: 450 min)
├─► Modelo 6:  Predice a 30 minutos  (ventana: 540 min)
├─► Modelo 7:  Predice a 35 minutos  (ventana: 630 min)
├─► Modelo 8:  Predice a 40 minutos  (ventana: 720 min)
├─► Modelo 9:  Predice a 45 minutos  (ventana: 810 min)
├─► Modelo 10: Predice a 50 minutos  (ventana: 900 min)
├─► Modelo 11: Predice a 55 minutos  (ventana: 990 min)
└─► Modelo 12: Predice a 60 minutos  (ventana: 1440 min)

Ventaja: Cada modelo se especializa en su horizonte temporal
```

**Arquitectura del Modelo Bi-LSTM**:

```
INPUT: (batch_size, ventana_variable, 5 features)
│
├─► Bidirectional LSTM (128 units)
│   └─► Output: (batch_size, ventana, 256)
├─► Dropout (0.2)
├─► Batch Normalization
│
├─► Bidirectional LSTM (64 units)
│   └─► Output: (batch_size, 128)
├─► Dropout (0.2)
├─► Batch Normalization
│
├─► Dense (64, relu)
├─► Dropout (0.2)
├─► Dense (32, relu)
└─► Dense (5, linear)
    └─► OUTPUT: [open, high, low, close, volume]

Total params: ~313,605 (1.20 MB por modelo)
```

**Flujo de Predicción (Cada Hora)**:

```
HORA: XX:00 (ej: 14:00)

1. VERIFICACIÓN
   └─► ¿Ya hay predicciones para esta hora?
       ├─► SÍ: Skip (ya ejecutado)
       └─► NO: Continuar

2. VALIDACIÓN DE MODELOS
   └─► ¿Existen 12 modelos entrenados hoy?
       ├─► SÍ: Cargar modelos existentes
       └─► NO: Entrenar 12 modelos nuevos
           ├─► Tiempo: ~30-45 min/símbolo
           ├─► Datos: Hasta hora actual - 1h
           └─► Guardar en /app/models/{symbol}/

3. GENERACIÓN DE PREDICCIONES
   └─► Para cada minuto de la próxima hora (60 predicciones):
       ├─► Minuto 1 (XX:01): Usar modelo 5min
       ├─► Minuto 2 (XX:02): Usar modelo 10min
       ├─► ...
       ├─► Minuto 60 (XX+1:00): Usar modelo 60min
       └─► Algoritmo de selección según distancia al horizonte

4. ALMACENAMIENTO
   └─► Insertar 60 documentos en prediccion_{symbol}
       {
         "open_time": timestamp_minuto,
         "close": precio_predicho,
         "predicted_at": "2025-11-17T14:00:01Z",
         "minutes_ahead": horizonte_usado
       }
```

**Arquitectura Interna**:

```
predictor/
├── main.py                   # Scheduler, ejecución horaria
├── prediction_service.py     # Orquestador del proceso
├── lstm_predictor.py         # Implementación Bi-LSTM
├── model_manager.py          # Gestión de modelos
├── data_processor.py         # Preprocesamiento de datos
├── mongo_client.py           # Cliente MongoDB (PyMongo)
├── config.py                 # Configuración
└── logger_config.py          # Sistema de logging
```

---

### 5. Frontend (Web App)

**Propósito**: Visualización interactiva de datos y predicciones en tiempo real

**Especificaciones**:
- **Servidor**: Nginx 1.25
- **Container**: binance_frontend
- **IP**: 192.168.31.14
- **Puerto**: 8080
- **Health Check**: HTTP GET /health cada 30s

**Stack Frontend**:
- **HTML5**: Estructura semántica
- **CSS3**: Estilos responsivos
- **JavaScript (Vanilla)**: Sin frameworks pesados
- **Chart.js 4.4**: Visualización de gráficos
- **WebSocket API**: Conexión en tiempo real con backend

**Características**:
- **Chart Interactivo**: Zoom, pan, tooltips
- **Actualización Automática**: Vía WebSocket
- **Selector de Monedas**: BTCUSDT, ETHUSDT, BNBUSDT
- **Rangos de Tiempo**: 15min, 30min, 1h, día, semana, mes, año
- **Comparación Visual**: Línea azul (real) vs línea roja (predicción)
- **Indicadores de Estado**: Conexión WebSocket, última actualización

---

## Flujo de Datos

### Flujo de Sincronización (Cada Minuto)

```
┌─────────────────────────────────────────────────────────────────┐
│  TIEMPO: XX:XX (Cada 60 segundos)                               │
└─────────────────────────────────────────────────────────────────┘

1. COIN SYNC (Scheduler)
   └─► Ejecuta cada 60 segundos automáticamente

2. COIN SYNC → BACKEND
   └─► POST /api/sync {"symbol": "BTCUSDT"}

3. BACKEND (SyncDataHandler)
   ├─► Consulta último timestamp en MongoDB
   │   └─► db.klines_btcusdt.findOne({}, {sort: {open_time: -1}})
   ├─► Calcula rango faltante (last_time + 1ms hasta now)
   ├─► Solicita a Binance API:
   │   └─► GET https://api.binance.com/api/v3/klines
   │       ?symbol=BTCUSDT&interval=1m&startTime=X&endTime=Y
   ├─► Recibe klines nuevos (usualmente 1 registro)
   ├─► Inserta en MongoDB (upsert):
   │   └─► db.klines_btcusdt.updateMany(..., upsert=true)
   └─► Calcula estadísticas actualizadas

4. BACKEND (WebSocketManager)
   └─► Broadcast a todos los clientes suscritos a BTCUSDT:
       {
         "type": "sync_complete",
         "symbol": "BTCUSDT",
         "timestamp": "2025-11-17T14:30:00Z",
         "statistics": {
           "new_records": 1,
           "total_records": 244238,
           "last_price": 94874.0
         }
       }

5. FRONTEND (WebSocket Clients)
   ├─► Recibe notificación
   ├─► Extrae last_price y timestamp
   ├─► Hace fetch incremental:
   │   └─► GET /api/data/BTCUSDT?start_time={last_timestamp}&limit=1
   └─► Actualiza chart sin animación (ventana deslizante)
```

### Flujo de Predicción (Cada Hora)

```
┌─────────────────────────────────────────────────────────────────┐
│  TIEMPO: XX:00 (Cada hora en punto)                             │
└─────────────────────────────────────────────────────────────────┘

1. PREDICTOR (Scheduler)
   └─► Se ejecuta automáticamente cada hora en punto

2. PREDICTOR → MONGODB
   └─► Verifica predicciones existentes para esta hora:
       db.prediccion_btcusdt.find({
         predicted_at: {$gte: "2025-11-17T14:00:00Z"}
       })
       ├─► Si existen: Skip
       └─► Si no existen: Continuar

3. VALIDAR/ENTRENAR MODELOS
   ├─► Verificar si existen 12 modelos entrenados hoy
   │   └─► Buscar en /app/models/btcusdt/model_h{5-60}_20251117.keras
   ├─► Si no existen o están obsoletos:
   │   ├─► Obtener datos hasta hora_actual - 1h
   │   │   └─► db.klines_btcusdt.find({open_time: {$lte: X}})
   │   ├─► Para cada horizonte (5, 10, 15, ..., 60):
   │   │   ├─► Preparar ventana específica (90-1440 min)
   │   │   ├─► Normalizar con MinMaxScaler
   │   │   ├─► Entrenar Bi-LSTM (100 epochs, early stopping)
   │   │   └─► Guardar modelo + scaler + metadata
   │   └─► Total: ~30-45 minutos para entrenar 12 modelos

4. GENERAR PREDICCIONES (60 minutos)
   └─► Obtener datos históricos (ventana más grande: 1440 min)
   └─► Para cada minuto de la próxima hora:
       ├─► Seleccionar modelo según distancia al horizonte
       ├─► Preparar input (ventana del modelo)
       ├─► Predecir [open, high, low, close, volume]
       └─► Almacenar predicción con minutes_ahead

5. GUARDAR EN MONGODB
   └─► Insertar 60 documentos:
       db.prediccion_btcusdt.insertMany([
         {
           open_time: timestamp_14_01,
           close: 94880.5,
           predicted_at: "2025-11-17T14:00:01Z",
           minutes_ahead: 5
         },
         ...
       ])

6. FRONTEND (Consulta Posterior)
   └─► GET /api/predictions/BTCUSDT
   └─► Renderiza línea de predicción en el chart
```

---

## Base de Datos

### Colecciones MongoDB

#### klines_{symbol}

**Propósito**: Datos históricos reales de precios

**Índices**:
```javascript
db.klines_btcusdt.createIndex({ "open_time": 1 }, { unique: true })
db.klines_btcusdt.createIndex({ "close_time": 1 })
db.klines_btcusdt.createIndex({ "timestamp": 1 })
```

**Tamaño aproximado**: ~240k registros por símbolo (desde junio 2025)

#### prediccion_{symbol}

**Propósito**: Predicciones generadas por modelos LSTM

**Índices**:
```javascript
db.prediccion_{symbol}.createIndex({ "open_time": 1 }, { unique: true })
db.prediccion_{symbol}.createIndex({ "predicted_at": 1 })
db.prediccion_{symbol}.createIndex({ "minutes_ahead": 1 })
```

**Tamaño aproximado**: ~1440 registros por día por símbolo

---

## Red Docker

### Configuración de Red

```yaml
networks:
  cripto_net:
    driver: bridge
    ipam:
      config:
        - subnet: 192.168.31.0/24
          gateway: 192.168.31.1
```

### Asignación de IPs

| Servicio | IP | Puerto Interno | Puerto Externo |
|----------|----|-----------------|-----------------
| MongoDB | 192.168.31.10 | 27017 | 21018 |
| Backend | 192.168.31.11 | 8888 | 8888 |
| Coin Sync | 192.168.31.12 | - | - |
| Predictor | 192.168.31.13 | - | - |
| Frontend | 192.168.31.14 | 80 | 8080 |

---

## Comunicaciones

### REST API (Backend)

- **Protocolo**: HTTP/1.1
- **Formato**: JSON
- **CORS**: Habilitado para todos los orígenes
- **Timeout**: 300s para operaciones largas

### WebSocket (Backend)

- **Protocolo**: WebSocket (ws://)
- **Formato**: JSON
- **Heartbeat**: Ping/Pong cada 30s
- **Reconnect**: Automático con backoff exponencial

### MongoDB

- **Protocolo**: MongoDB Wire Protocol
- **Autenticación**: SCRAM-SHA-256
- **Driver Backend**: Motor (async)
- **Driver Predictor**: PyMongo (sync)

---

## Escalabilidad

### Escalado Horizontal (Futuro)

#### Backend con Redis Pub/Sub

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Backend  │     │ Backend  │     │ Backend  │
│ Instance │     │ Instance │     │ Instance │
│    1     │     │    2     │     │    3     │
└────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │
     └────────────────┼────────────────┘
                      │
                ┌─────▼──────┐
                │   Redis    │
                │  Pub/Sub   │
                └────────────┘

Ventajas:
- Escala a 100k+ conexiones WebSocket
- Load balancing automático
- Fault tolerance
```

#### Predictor con Queue

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│Predictor │     │Predictor │     │Predictor │
│Worker 1  │     │Worker 2  │     │Worker 3  │
└────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │
     └────────────────┼────────────────┘
                      │
                ┌─────▼──────┐
                │   RabbitMQ │
                │   / Redis  │
                │   Queue    │
                └────────────┘

Ventajas:
- Paralelización de entrenamientos
- Distribución de carga
- Reintentos automáticos
```

### Límites Actuales

| Componente | Límite | Solución para Escalar |
|------------|--------|------------------------|
| Backend WebSocket | ~10k conexiones | Redis Pub/Sub |
| Predictor | 1 símbolo a la vez | Queue + Workers |
| MongoDB | ~1M documentos | Sharding |
| Coin Sync | 3 símbolos | Múltiples instancias |

---

## Resumen Ejecutivo

### Arquitectura Actual

- **4 Servicios Dockerizados**: MongoDB, Backend, Coin Sync, Predictor, Frontend
- **Comunicación Asíncrona**: Tornado + Motor + aiohttp
- **Predicción Avanzada**: 12 modelos Bi-LSTM por símbolo
- **Tiempo Real**: WebSocket con sistema de suscripciones
- **Persistencia**: Volúmenes Docker para datos y modelos

### Métricas de Rendimiento

- **Latencia WebSocket**: < 100ms
- **Throughput Backend**: ~1000 req/s
- **Precisión LSTM**: R²=0.95, MAPE<3%
- **Almacenamiento**: ~1 GB/mes/símbolo
- **Memoria Predictor**: ~10 GB durante entrenamiento

---

**Documento actualizado**: Noviembre 2025
**Versión del sistema**: 2.0
