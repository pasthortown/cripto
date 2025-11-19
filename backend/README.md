# Backend de Binance - API REST

Backend desarrollado en Python con Tornado que se conecta al API público de Binance para obtener y almacenar datos históricos de criptomonedas.

## Características

- **Framework**: Tornado (servidor web asíncrono)
- **Base de datos**: MongoDB (cada moneda en una colección separada)
- **Sincronización incremental**: Valida datos existentes y obtiene solo los faltantes
- **Containerización**: Docker y Docker Compose
- **Red personalizada**: cripto_net (192.168.31.0/24)
- **Intervalos**: 1 minuto
- **Fecha inicial**: 1 de junio de 2025

## Estructura del Proyecto

```
backend/
├── app/
│   ├── binance_client.py    # Cliente para Binance API
│   ├── db_client.py          # Cliente para MongoDB
│   ├── handlers.py           # Handlers de Tornado (endpoints)
│   ├── config.py             # Configuración
│   └── main.py               # Aplicación principal
├── tests/
│   ├── test_binance_client.py
│   └── test_db_client.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Endpoints Disponibles

### 1. Health Check
```
GET /health
```
Verifica el estado del servicio y la conexión con MongoDB.

**Respuesta:**
```json
{
  "status": "healthy",
  "service": "binance-backend",
  "database": "connected"
}
```

### 2. Sincronizar Datos
```
POST /api/sync
```
Sincroniza datos de una moneda desde Binance.

**Body:**
```json
{
  "symbol": "BTCUSDT"
}
```

**Respuesta:**
```json
{
  "success": true,
  "symbol": "BTCUSDT",
  "new_records": 1500,
  "statistics": {
    "symbol": "BTCUSDT",
    "total_records": 1500,
    "first_record": "2025-06-01T00:00:00+00:00",
    "last_record": "2025-06-01T02:00:00+00:00"
  }
}
```

### 3. Obtener Datos
```
GET /api/data/{symbol}?start_time={timestamp}&end_time={timestamp}&limit={limit}
```
Obtiene datos almacenados de una moneda.

**Parámetros:**
- `symbol`: Par de trading (BTCUSDT, ETHUSDT, etc.)
- `start_time` (opcional): Timestamp en milisegundos
- `end_time` (opcional): Timestamp en milisegundos
- `limit` (opcional): Cantidad máxima de registros

**Respuesta:**
```json
{
  "success": true,
  "symbol": "BTCUSDT",
  "count": 100,
  "data": [
    {
      "open_time": 1717200000000,
      "open": 67000.0,
      "high": 67500.0,
      "low": 66500.0,
      "close": 67200.0,
      "volume": 100.5,
      "close_time": 1717200059999,
      "timestamp": "2025-06-01T00:00:00+00:00"
    }
  ]
}
```

### 4. Obtener Estadísticas
```
GET /api/stats/{symbol}
```
Obtiene estadísticas de los datos almacenados.

**Respuesta:**
```json
{
  "success": true,
  "statistics": {
    "symbol": "BTCUSDT",
    "total_records": 1500,
    "first_record": "2025-06-01T00:00:00+00:00",
    "last_record": "2025-06-01T02:00:00+00:00"
  }
}
```

## Instalación y Uso

### Prerrequisitos
- Docker
- Docker Compose

### Iniciar los servicios

1. Construir y levantar los contenedores:
```bash
cd backend
docker-compose up --build
```

2. El API estará disponible en: `http://localhost:8888`
3. MongoDB estará disponible en: `localhost:21018`

### Ejecutar prueba con BTCUSDT

```bash
curl -X POST http://localhost:8888/api/sync \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT"}'
```

### Verificar estadísticas

```bash
curl http://localhost:8888/api/stats/BTCUSDT
```

## Pruebas Unitarias

### Ejecutar todas las pruebas

```bash
# Dentro del contenedor
docker-compose exec backend pytest

# O localmente (requiere MongoDB corriendo)
pytest
```

### Ejecutar pruebas con cobertura

```bash
pytest --cov=app --cov-report=html
```

## Configuración de Red

La aplicación utiliza una red Docker personalizada:

- **Nombre**: cripto_net
- **Subnet**: 192.168.31.0/24
- **Gateway**: 192.168.31.1
- **MongoDB**: 192.168.31.10
- **Backend**: 192.168.31.11

## Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `MONGODB_HOST` | Host de MongoDB | mongodb |
| `MONGODB_PORT` | Puerto de MongoDB | 27017 |
| `MONGODB_DATABASE` | Base de datos | binance_data |
| `MONGODB_USERNAME` | Usuario de MongoDB | (requerido) |
| `MONGODB_PASSWORD` | Contraseña de MongoDB | (requerido) |
| `SERVER_PORT` | Puerto del servidor | 8888 |
| `LOG_LEVEL` | Nivel de logging | INFO |

## Notas Técnicas

### Sincronización Incremental
El sistema verifica automáticamente los datos existentes en MongoDB:
- Si hay datos: obtiene desde el último timestamp hasta ahora
- Si no hay datos: obtiene desde el 1-6-2025 hasta ahora

### Manejo de Duplicados
- Los datos se insertan usando `upsert` con `open_time` como clave única
- Los duplicados se ignoran automáticamente

### Límites de la API de Binance
- Máximo 1000 registros por request
- El cliente maneja automáticamente múltiples requests para rangos grandes

### Persistencia
- Los datos de MongoDB se almacenan en un volumen Docker
- Los datos persisten aunque se detengan los contenedores

## Detener los servicios

```bash
docker-compose down
```

Para eliminar también los volúmenes (datos):
```bash
docker-compose down -v
```

## Autor

Backend desarrollado con Python, Tornado, MongoDB y Docker para consumir datos de Binance API.
