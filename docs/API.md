# API Documentation - Binance Crypto Predictor

**Documentación completa de endpoints REST y WebSocket**

Versión: 2.0
Base URL: `http://localhost:8888`

---

## Tabla de Contenidos

1. [REST API Endpoints](#rest-api-endpoints)
2. [WebSocket API](#websocket-api)
3. [Modelos de Datos](#modelos-de-datos)
4. [Códigos de Error](#códigos-de-error)
5. [Ejemplos de Uso](#ejemplos-de-uso)

---

## REST API Endpoints

### Health Check

**GET** `/health`

Verifica el estado del servicio y la conexión con MongoDB.

**Response 200 OK**:
```json
{
  "status": "healthy",
  "service": "binance-backend",
  "database": "connected"
}
```

**Response 503 Service Unavailable**:
```json
{
  "status": "unhealthy",
  "service": "binance-backend",
  "database": "disconnected",
  "error": "Connection timeout"
}
```

---

### Listar Símbolos Disponibles

**GET** `/api/symbols`

Obtiene la lista de todas las criptomonedas con datos en el sistema.

**Response 200 OK**:
```json
{
  "success": true,
  "count": 3,
  "symbols": [
    {
      "symbol": "BTCUSDT",
      "total_records": 244238,
      "first_record": "2025-06-01T00:00:00+00:00",
      "last_record": "2025-11-17T14:45:00+00:00",
      "last_price": 94874.0
    },
    {
      "symbol": "ETHUSDT",
      "total_records": 244238,
      "first_record": "2025-06-01T00:00:00+00:00",
      "last_record": "2025-11-17T14:45:00+00:00",
      "last_price": 3155.46
    },
    {
      "symbol": "BNBUSDT",
      "total_records": 244236,
      "first_record": "2025-06-01T00:00:00+00:00",
      "last_record": "2025-11-17T14:45:00+00:00",
      "last_price": 918.92
    }
  ]
}
```

---

### Sincronizar Datos

**POST** `/api/sync`

Sincroniza datos de una criptomoneda desde Binance API.

**Request Body**:
```json
{
  "symbol": "BTCUSDT"
}
```

**Response 200 OK**:
```json
{
  "success": true,
  "symbol": "BTCUSDT",
  "new_records": 5,
  "statistics": {
    "symbol": "BTCUSDT",
    "total_records": 244238,
    "first_record": "2025-06-01T00:00:00+00:00",
    "last_record": "2025-11-17T14:45:00+00:00",
    "last_price": 94874.0
  }
}
```

**Response 400 Bad Request**:
```json
{
  "success": false,
  "error": "Symbol is required"
}
```

**Notas**:
- Notifica automáticamente a clientes WebSocket suscritos
- Sincronización incremental (solo datos faltantes)
- Maneja automáticamente el límite de 1000 registros de Binance

---

### Obtener Datos Históricos

**GET** `/api/data/{symbol}`

Obtiene datos históricos de klines (velas) de una criptomoneda.

**Path Parameters**:
- `symbol`: Símbolo de la moneda (BTCUSDT, ETHUSDT, BNBUSDT)

**Query Parameters**:
- `start_time` (opcional): Timestamp inicio en milisegundos
- `end_time` (opcional): Timestamp fin en milisegundos
- `limit` (opcional): Cantidad máxima de registros (default: sin límite)

**Ejemplos**:
```
GET /api/data/BTCUSDT?limit=100
GET /api/data/BTCUSDT?start_time=1731542400000&end_time=1731628799999
GET /api/data/BTCUSDT?start_time=1731542400000&limit=1000
```

**Response 200 OK**:
```json
{
  "success": true,
  "symbol": "BTCUSDT",
  "count": 100,
  "data": [
    {
      "open_time": 1731628800000,
      "open": 100000.50,
      "high": 100500.00,
      "low": 99800.00,
      "close": 100200.00,
      "volume": 1500.25,
      "close_time": 1731628859999,
      "quote_asset_volume": "150150000.50",
      "number_of_trades": 1234,
      "taker_buy_base_asset_volume": "750.12",
      "taker_buy_quote_asset_volume": "75075000.25",
      "timestamp": "2025-11-17T14:00:00+00:00"
    }
  ]
}
```

**Response 404 Not Found**:
```json
{
  "success": false,
  "error": "Symbol not found: XXXUSDT"
}
```

---

### Obtener Predicciones

**GET** `/api/predictions/{symbol}`

Obtiene predicciones generadas por el modelo LSTM.

**Path Parameters**:
- `symbol`: Símbolo de la moneda

**Query Parameters**:
- `start_time` (opcional): Timestamp inicio en milisegundos
- `end_time` (opcional): Timestamp fin en milisegundos
- `limit` (opcional): Cantidad máxima de registros

**Response 200 OK**:
```json
{
  "success": true,
  "symbol": "BTCUSDT",
  "count": 60,
  "data": [
    {
      "open_time": 1731628800000,
      "open": 100150.25,
      "high": 100450.30,
      "low": 99900.50,
      "close": 100250.75,
      "volume": 1480.50,
      "close_time": 1731628859999,
      "predicted_at": "2025-11-17T14:00:01Z",
      "model_version": "Bi-LSTM",
      "minutes_ahead": 5
    }
  ]
}
```

**Notas**:
- Las predicciones se generan cada hora en punto
- Campo `minutes_ahead` indica el horizonte de predicción usado (5-60)
- Si no hay predicciones, retorna `count: 0, data: []`

---

### Obtener Estadísticas

**GET** `/api/stats/{symbol}`

Obtiene estadísticas de una criptomoneda.

**Path Parameters**:
- `symbol`: Símbolo de la moneda

**Response 200 OK**:
```json
{
  "success": true,
  "statistics": {
    "symbol": "BTCUSDT",
    "total_records": 244238,
    "first_record": "2025-06-01T00:00:00+00:00",
    "last_record": "2025-11-17T14:45:00+00:00",
    "last_price": 94874.0
  }
}
```

---

## WebSocket API

### Conexión

**URL**: `ws://localhost:8888/ws/updates`

**Establecer Conexión**:
```javascript
const ws = new WebSocket('ws://localhost:8888/ws/updates');

ws.onopen = () => {
    console.log('Conectado al servidor WebSocket');
};

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    handleMessage(message);
};

ws.onerror = (error) => {
    console.error('Error WebSocket:', error);
};

ws.onclose = () => {
    console.log('Conexión cerrada');
    // Implementar reconnect automático
};
```

---

### Mensajes del Cliente

#### Suscribirse a Símbolos

```json
{
  "action": "subscribe",
  "symbols": ["BTCUSDT", "ETHUSDT"]
}
```

**Response**:
```json
{
  "type": "subscribed",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "timestamp": "2025-11-17T14:45:00Z"
}
```

#### Desuscribirse

```json
{
  "action": "unsubscribe",
  "symbols": ["BTCUSDT"]
}
```

**Response**:
```json
{
  "type": "unsubscribed",
  "symbols": ["BTCUSDT"],
  "timestamp": "2025-11-17T14:45:00Z"
}
```

#### Heartbeat (Ping)

```json
{
  "action": "ping"
}
```

**Response**:
```json
{
  "type": "pong",
  "timestamp": "2025-11-17T14:45:00Z"
}
```

#### Obtener Estadísticas del Servidor

```json
{
  "action": "stats"
}
```

**Response**:
```json
{
  "type": "stats",
  "data": {
    "total_connections": 15,
    "subscriptions": {
      "BTCUSDT": 10,
      "ETHUSDT": 8,
      "BNBUSDT": 5
    }
  },
  "timestamp": "2025-11-17T14:45:00Z"
}
```

---

### Mensajes del Servidor

#### Conexión Establecida

```json
{
  "type": "connected",
  "message": "Conectado al servidor de actualizaciones de Binance",
  "timestamp": "2025-11-17T14:45:00Z"
}
```

#### Sincronización Completada

**Enviado automáticamente cuando coin_sync sincroniza datos**

```json
{
  "type": "sync_complete",
  "symbol": "BTCUSDT",
  "timestamp": "2025-11-17T14:45:00Z",
  "statistics": {
    "new_records": 1,
    "total_records": 244238,
    "last_price": 94874.0,
    "last_record": "2025-11-17T14:45:00+00:00"
  }
}
```

**Solo lo reciben clientes suscritos al símbolo**

#### Error

```json
{
  "type": "error",
  "message": "Acción desconocida: foo",
  "timestamp": "2025-11-17T14:45:00Z"
}
```

---

## Modelos de Datos

### Kline (Datos Históricos)

```typescript
interface Kline {
  open_time: number;              // Timestamp inicio (ms)
  open: number;                   // Precio apertura
  high: number;                   // Precio máximo
  low: number;                    // Precio mínimo
  close: number;                  // Precio cierre
  volume: number;                 // Volumen
  close_time: number;             // Timestamp cierre (ms)
  quote_asset_volume: string;     // Volumen cotizado
  number_of_trades: number;       // Número de trades
  taker_buy_base_asset_volume: string;
  taker_buy_quote_asset_volume: string;
  timestamp: string;              // ISO 8601
}
```

### Prediction (Predicción)

```typescript
interface Prediction {
  open_time: number;              // Timestamp inicio (ms)
  open: number;                   // Precio apertura predicho
  high: number;                   // Precio máximo predicho
  low: number;                    // Precio mínimo predicho
  close: number;                  // Precio cierre predicho
  volume: number;                 // Volumen predicho
  close_time: number;             // Timestamp cierre (ms)
  predicted_at: string;           // Cuándo se generó (ISO 8601)
  model_version: string;          // "Bi-LSTM"
  minutes_ahead: number;          // Horizonte usado (5-60)
}
```

---

## Códigos de Error

| Código | Descripción | Solución |
|--------|-------------|----------|
| 400 | Bad Request | Verificar formato del body |
| 404 | Not Found | Verificar que el símbolo exista |
| 500 | Internal Server Error | Revisar logs del servidor |
| 503 | Service Unavailable | Backend o MongoDB no disponibles |

---

## Ejemplos de Uso

### cURL

```bash
# Health check
curl http://localhost:8888/health

# Listar símbolos
curl http://localhost:8888/api/symbols

# Sincronizar BTCUSDT
curl -X POST http://localhost:8888/api/sync \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT"}'

# Últimos 100 registros
curl "http://localhost:8888/api/data/BTCUSDT?limit=100"

# Predicciones del día
curl http://localhost:8888/api/predictions/BTCUSDT

# Estadísticas
curl http://localhost:8888/api/stats/BTCUSDT
```

### JavaScript (Fetch API)

```javascript
// Obtener datos históricos
async function getHistoricalData(symbol, limit = 100) {
  const response = await fetch(
    `http://localhost:8888/api/data/${symbol}?limit=${limit}`
  );
  const data = await response.json();
  return data.data;
}

// Obtener predicciones
async function getPredictions(symbol) {
  const response = await fetch(
    `http://localhost:8888/api/predictions/${symbol}`
  );
  const data = await response.json();
  return data.data;
}

// Sincronizar datos
async function syncSymbol(symbol) {
  const response = await fetch('http://localhost:8888/api/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol })
  });
  return await response.json();
}
```

### JavaScript (WebSocket)

```javascript
class BinanceWebSocket {
  constructor() {
    this.ws = new WebSocket('ws://localhost:8888/ws/updates');
    this.setupHandlers();
  }

  setupHandlers() {
    this.ws.onopen = () => {
      console.log('Connected');
      this.subscribe(['BTCUSDT', 'ETHUSDT']);
    };

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      this.handleMessage(msg);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('Connection closed, reconnecting...');
      setTimeout(() => this.reconnect(), 5000);
    };
  }

  subscribe(symbols) {
    this.send({ action: 'subscribe', symbols });
  }

  handleMessage(msg) {
    switch (msg.type) {
      case 'connected':
        console.log('Connection established');
        break;
      case 'subscribed':
        console.log('Subscribed to:', msg.symbols);
        break;
      case 'sync_complete':
        console.log('New data available for', msg.symbol);
        this.onNewData(msg);
        break;
    }
  }

  onNewData(msg) {
    // Implementar lógica para actualizar UI
    console.log('Statistics:', msg.statistics);
  }

  send(message) {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }
}

// Uso
const binanceWS = new BinanceWebSocket();
```

---

**Documentación actualizada**: Noviembre 2025
**Versión del API**: 2.0
