# Proyecto Binance - Sistema de Análisis de Criptomonedas

Sistema completo para obtener, almacenar y analizar datos históricos de criptomonedas desde la API pública de Binance.

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network                       │
│                cripto_net (192.168.31.0/24)            │
│                                                          │
│  ┌──────────────────┐         ┌──────────────────┐    │
│  │   MongoDB        │         │   Backend API    │    │
│  │  192.168.31.10   │◄────────┤  192.168.31.11   │    │
│  │  Puerto: 21018   │         │  Puerto: 8888    │    │
│  └──────────────────┘         └──────────────────┘    │
│         ▲                              ▲                │
└─────────┼──────────────────────────────┼────────────────┘
          │                              │
          │                              │
    Almacenamiento                  API Binance
    Persistente                     (Público)
```

## Componentes

### Backend (Python + Tornado)
- **Framework**: Tornado (asíncrono)
- **Lenguaje**: Python 3.11
- **Base de datos**: MongoDB con autenticación
- **API**: RESTful
- **Containerización**: Docker

### Base de Datos
- **MongoDB 7.0**: Con autenticación habilitada
- **Colecciones**: Una por cada par de trading
- **Índices**: Optimizados para consultas temporales

## Estructura del Proyecto

```
binance/
├── backend/                    # Código del backend
│   ├── app/
│   │   ├── binance_client.py  # Cliente Binance API
│   │   ├── db_client.py        # Cliente MongoDB
│   │   ├── handlers.py         # Endpoints REST
│   │   ├── config.py           # Configuración
│   │   └── main.py             # App principal
│   ├── tests/                  # Pruebas unitarias
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
├── docker-compose.yml          # Orquestación de servicios
├── .env                        # Variables de entorno (no en git)
├── .env.example                # Ejemplo de variables
└── README.md                   # Este archivo
```

## Inicio Rápido

### 1. Configurar Variables de Entorno

```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar .env con tus credenciales
# IMPORTANTE: Cambiar MONGODB_ROOT_PASSWORD por una contraseña segura
```

### 2. Iniciar los Servicios

```bash
# Construir y levantar todos los contenedores
docker-compose up --build

# O en modo detached (segundo plano)
docker-compose up -d --build
```

### 3. Verificar que los Servicios Estén Corriendo

```bash
# Verificar estado de los contenedores
docker-compose ps

# Ver logs
docker-compose logs -f

# Ver logs solo del backend
docker-compose logs -f backend
```

### 4. Probar el API

#### Health Check
```bash
curl http://localhost:8888/health
```

#### Sincronizar Datos de BTCUSDT
```bash
curl -X POST http://localhost:8888/api/sync \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT"}'
```

#### Ver Estadísticas
```bash
curl http://localhost:8888/api/stats/BTCUSDT
```

#### Obtener Datos
```bash
# Primeros 10 registros
curl http://localhost:8888/api/data/BTCUSDT?limit=10

# Con filtros de tiempo
curl "http://localhost:8888/api/data/BTCUSDT?start_time=1717200000000&limit=100"
```

## Endpoints del API

### GET /health
Verifica el estado del servicio.

**Respuesta:**
```json
{
  "status": "healthy",
  "service": "binance-backend",
  "database": "connected"
}
```

### POST /api/sync
Sincroniza datos de una moneda desde Binance.

**Request:**
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

### GET /api/data/{symbol}
Obtiene datos almacenados.

**Parámetros:**
- `symbol`: Par de trading (BTCUSDT, ETHUSDT, etc.)
- `start_time` (opcional): Timestamp en ms
- `end_time` (opcional): Timestamp en ms
- `limit` (opcional): Máx. registros

### GET /api/stats/{symbol}
Obtiene estadísticas de los datos.

## Scripts de Prueba

### PowerShell (Windows)
```powershell
.\backend\test_btcusdt.ps1
```

### Bash (Linux/Mac)
```bash
chmod +x backend/test_btcusdt.sh
./backend/test_btcusdt.sh
```

## Características Principales

### Sincronización Incremental
- Verifica datos existentes en MongoDB
- Obtiene solo los datos faltantes
- Si no hay datos: desde 1 de junio de 2025
- Si hay datos: desde el último registro

### Seguridad
- MongoDB con autenticación obligatoria
- Credenciales en archivo `.env` (no en git)
- Red Docker aislada
- Variables de entorno para configuración sensible

### Persistencia
- Volúmenes Docker para datos de MongoDB
- Los datos persisten aunque se detengan los contenedores
- Índices únicos para evitar duplicados

### Escalabilidad
- Servidor asíncrono (Tornado)
- Cliente HTTP asíncrono (aiohttp)
- Driver MongoDB asíncrono (Motor)
- Manejo automático de límites de API

## Configuración Avanzada

### Variables de Entorno (.env)

| Variable | Descripción | Default |
|----------|-------------|---------|
| `MONGODB_ROOT_USERNAME` | Usuario admin de MongoDB | admin |
| `MONGODB_ROOT_PASSWORD` | Contraseña de MongoDB | (requerido) |
| `MONGODB_DATABASE` | Nombre de la BD | binance_data |
| `MONGODB_PORT` | Puerto externo | 21018 |
| `SERVER_PORT` | Puerto del API | 8888 |
| `LOG_LEVEL` | Nivel de logs | INFO |
| `MONGODB_IP` | IP en red Docker | 192.168.31.10 |
| `BACKEND_IP` | IP en red Docker | 192.168.31.11 |

### Red Docker

- **Nombre**: cripto_net
- **Tipo**: bridge
- **Subnet**: 192.168.31.0/24
- **Gateway**: 192.168.31.1

## Desarrollo

### Ejecutar Pruebas Unitarias

```bash
# Dentro del contenedor backend
docker-compose exec backend pytest

# Con cobertura
docker-compose exec backend pytest --cov=app --cov-report=html

# Localmente (requiere MongoDB corriendo)
cd backend
pytest
```

### Acceder a MongoDB

```bash
# Con mongosh desde el contenedor
docker-compose exec mongodb mongosh -u admin -p SecurePass123! --authenticationDatabase admin

# Desde tu máquina (si tienes mongosh instalado)
mongosh "mongodb://admin:SecurePass123!@localhost:21018/?authSource=admin"
```

### Ver Logs en Tiempo Real

```bash
# Todos los servicios
docker-compose logs -f

# Solo backend
docker-compose logs -f backend

# Solo MongoDB
docker-compose logs -f mongodb
```

## Mantenimiento

### Detener los Servicios

```bash
# Detener contenedores
docker-compose down

# Detener y eliminar volúmenes (BORRA TODOS LOS DATOS)
docker-compose down -v
```

### Reiniciar un Servicio

```bash
# Solo el backend
docker-compose restart backend

# Solo MongoDB
docker-compose restart mongodb
```

### Reconstruir Imágenes

```bash
# Reconstruir todo
docker-compose up --build

# Reconstruir solo backend
docker-compose build backend
```

### Limpiar Sistema

```bash
# Eliminar contenedores detenidos
docker container prune

# Eliminar imágenes sin usar
docker image prune

# Eliminar todo (cuidado)
docker system prune -a
```

## Datos de Ejemplo

### Pares de Trading Soportados

Cualquier par disponible en Binance:
- BTCUSDT (Bitcoin)
- ETHUSDT (Ethereum)
- BNBUSDT (Binance Coin)
- ADAUSDT (Cardano)
- SOLUSDT (Solana)
- etc.

### Intervalos Configurados

- Por defecto: 1 minuto (1m)
- Modificable en `backend/app/config.py`

## Troubleshooting

### Error: "Cannot connect to MongoDB"
```bash
# Verificar que MongoDB esté corriendo
docker-compose ps

# Ver logs de MongoDB
docker-compose logs mongodb

# Verificar credenciales en .env
cat .env
```

### Error: "Port already in use"
```bash
# Cambiar los puertos en .env
# Ejemplo:
# MONGODB_PORT=21019
# SERVER_PORT=8889
```

### Error: "Authentication failed"
```bash
# Eliminar volúmenes y reconstruir
docker-compose down -v
docker-compose up --build
```

## Próximas Mejoras

- [ ] Frontend web para visualización
- [ ] Más endpoints de análisis
- [ ] WebSocket para datos en tiempo real
- [ ] Autenticación del API
- [ ] Rate limiting
- [ ] Caché de consultas frecuentes

## Tecnologías Utilizadas

- **Python 3.11**: Lenguaje principal
- **Tornado**: Framework web asíncrono
- **MongoDB 7.0**: Base de datos NoSQL
- **Motor**: Driver asíncrono de MongoDB
- **aiohttp**: Cliente HTTP asíncrono
- **Docker**: Containerización
- **Docker Compose**: Orquestación
- **pytest**: Testing

## Licencia

Proyecto educativo para análisis de datos de criptomonedas.

## Autor

Backend desarrollado con Python, Tornado y MongoDB.
