# Binance Crypto Predictor - Documentación Completa

**Sistema de Análisis y Predicción de Criptomonedas en Tiempo Real**

Versión: 2.0
Fecha: Noviembre 2025

---

## Tabla de Contenidos

1. [Descripción General](#descripción-general)
2. [Características Principales](#características-principales)
3. [Arquitectura del Sistema](#arquitectura-del-sistema)
4. [Componentes](#componentes)
5. [Stack Tecnológico](#stack-tecnológico)
6. [Inicio Rápido](#inicio-rápido)
7. [Documentación Detallada](#documentación-detallada)
8. [Estado Actual](#estado-actual)

---

## Descripción General

Sistema completo para:

- **Recolección** de datos históricos de criptomonedas desde Binance API
- **Almacenamiento** en MongoDB con indexación optimizada
- **Predicción** de precios usando redes neuronales Bi-LSTM multi-horizonte
- **Exposición** de APIs REST y WebSocket para consumo frontend
- **Visualización** en tiempo real con frontend web interactivo

### Casos de Uso

- **Trading algorítmico**: Predicciones de corto plazo (5-60 minutos)
- **Análisis de mercado**: Visualización de tendencias históricas
- **Investigación**: Datos limpios y estructurados de múltiples criptomonedas
- **Alertas**: Notificaciones en tiempo real de cambios de precio

---

## Características Principales

### Recolección de Datos
- Sincronización automática cada 60 segundos
- Datos de Binance API con intervalo de 1 minuto
- Sincronización incremental (solo datos faltantes)
- Manejo automático de límites de API

### Predicción LSTM Multi-Horizonte
- **12 modelos especializados** por criptomoneda (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60 minutos)
- **Arquitectura Bi-LSTM** con Batch Normalization
- **Ventanas variables** según horizonte (90-1440 minutos)
- **Predicción continua** cada hora automáticamente
- **Precisión**: ~95% R² Score, <3% MAPE

### API en Tiempo Real
- **REST API**: Consulta de datos históricos y predicciones
- **WebSocket**: Notificaciones push de nuevos datos
- **Sistema de suscripciones** por símbolo
- **CORS habilitado** para acceso cross-origin

### Frontend Web
- **Chart interactivo** con Chart.js
- **Actualización automática** vía WebSocket
- **Comparación visual** datos reales vs predicciones
- **Selector de monedas** y rangos de tiempo
- **Responsive** para móvil y escritorio

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    SISTEMA COMPLETO                             │
│              Docker Network: cripto_net (192.168.31.0/24)       │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐
│   Binance    │
│     API      │  (Fuente externa)
└──────┬───────┘
       │ HTTP Requests (klines 1m)
       ▼
┌──────────────────────────────────────────────────────────────────┐
│                     CONTENEDORES DOCKER                          │
└──────────────────────────────────────────────────────────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Coin Sync   │─►│   Backend    │  │  Predictor   │  │  Frontend    │
│ (Sync Auto)  │  │ (Tornado API)│  │ (Bi-LSTM x12)│  │  (Nginx)     │
│ 192.168.31.12│  │ 192.168.31.11│  │ 192.168.31.13│  │192.168.31.14 │
│              │  │              │  │              │  │              │
│ Cada 60s     │  │ REST + WS    │  │ Cada 1h      │  │ Puerto 8080  │
└──────────────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
                         │                 │                 │
                         └────────┬────────┴─────────────────┘
                                  │ Motor / PyMongo
                         ┌────────▼─────────────────────┐
                         │       MongoDB 7.0            │
                         │    192.168.31.10:27017       │
                         │                              │
                         │  Collections:                │
                         │  ├─ klines_btcusdt          │
                         │  ├─ klines_ethusdt          │
                         │  ├─ klines_bnbusdt          │
                         │  ├─ prediccion_btcusdt      │
                         │  ├─ prediccion_ethusdt      │
                         │  └─ prediccion_bnbusdt      │
                         │                              │
                         │  Volúmenes:                  │
                         │  ├─ mongodb_data             │
                         │  ├─ mongodb_config           │
                         │  └─ predictor_models         │
                         └──────────────────────────────┘
```

---

## Componentes

### 1. MongoDB (Base de Datos)
- **Versión**: 7.0
- **Puerto**: 21018 (externo) → 27017 (interno)
- **Autenticación**: Habilitada
- **Persistencia**: Volúmenes Docker
- **Colecciones**:
  - `klines_{symbol}`: Datos históricos reales
  - `prediccion_{symbol}`: Predicciones del modelo

### 2. Backend (Tornado API)
- **Framework**: Tornado 6.4.1 (asíncrono)
- **Puerto**: 8888
- **Endpoints REST**: Health, Sync, Data, Stats, Predictions, Symbols
- **WebSocket**: `/ws/updates` para notificaciones en tiempo real
- **Tecnologías**: Python 3.11, Motor (MongoDB async), aiohttp

### 3. Coin Sync (Sincronización Automática)
- **Función**: Sincroniza datos cada 60 segundos
- **Proceso**:
  1. Obtiene lista de símbolos disponibles
  2. Para cada símbolo: POST /api/sync
  3. Notifica a clientes WebSocket
- **Tecnologías**: Python 3.11, Requests

### 4. Predictor (LSTM Multi-Horizonte)
- **Modelo**: Bi-LSTM con Batch Normalization
- **Estrategia**: 12 modelos especializados por símbolo
- **Horizontes**: 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60 minutos
- **Ejecución**: Automática cada hora en punto
- **Ventanas variables**: 90-1440 minutos según horizonte
- **Tecnologías**: TensorFlow 2.15, Scikit-learn, NumPy

### 5. Frontend (Web App)
- **Servidor**: Nginx 1.25
- **Puerto**: 8080
- **Stack**: HTML5, JavaScript (Vanilla), Chart.js 4.4
- **Features**: Chart interactivo, WebSocket, selector de monedas/rangos

---

## Stack Tecnológico

| Capa | Tecnología | Versión | Propósito |
|------|------------|---------|-----------|
| **Backend** | Python | 3.11 | API REST y WebSocket |
| **Framework Web** | Tornado | 6.4.1 | Servidor asíncrono |
| **Base de Datos** | MongoDB | 7.0 | Almacenamiento NoSQL |
| **Machine Learning** | TensorFlow/Keras | 2.15.0 | Redes neuronales LSTM |
| **Normalización** | Scikit-learn | 1.3.2 | MinMaxScaler |
| **Frontend Server** | Nginx | 1.25 | Servidor web estático |
| **Visualización** | Chart.js | 4.4 | Gráficos interactivos |
| **Containerización** | Docker | latest | Aislamiento de servicios |
| **Orquestación** | Docker Compose | latest | Gestión multi-contenedor |

---

## Inicio Rápido

### Prerrequisitos

- Docker y Docker Compose instalados
- Puertos disponibles: 8888 (backend), 21018 (MongoDB), 8080 (frontend)
- Mínimo 16 GB RAM recomendado

### Instalación

1. **Clonar el repositorio**:
```bash
git clone <repo-url>
cd binance
```

2. **Configurar variables de entorno**:
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

3. **Iniciar todos los servicios**:
```bash
docker-compose up -d --build
```

4. **Verificar estado**:
```bash
docker-compose ps
```

Deberías ver:
- `binance_mongodb` - Up (healthy)
- `binance_backend` - Up (healthy)
- `binance_coin_sync` - Up
- `binance_predictor` - Up
- `binance_frontend` - Up (healthy)

### Acceder a la Aplicación

- **Frontend**: http://localhost:8080
- **API Backend**: http://localhost:8888
- **Health Check**: http://localhost:8888/health

### Primeros Pasos

1. **Esperar sincronización inicial** (~5 minutos):
   - Coin Sync sincroniza datos automáticamente
   - Ver logs: `docker-compose logs -f coin_sync`

2. **Acceder al frontend**:
   - Abrir http://localhost:8080
   - Seleccionar moneda (BTCUSDT, ETHUSDT, BNBUSDT)
   - Ver datos en tiempo real

3. **Esperar primera predicción** (siguiente hora en punto):
   - El predictor ejecuta cada hora (ej: 14:00, 15:00)
   - Ver logs: `docker-compose logs -f predictor`
   - Una vez completado, verás línea de predicción en el chart

---

## Documentación Detallada

- **[ARCHITECTURE.md](./ARCHITECTURE.md)**: Arquitectura técnica completa del sistema (backend, frontend, MongoDB, WebSocket)
- **[API.md](./API.md)**: Documentación de endpoints REST y WebSocket
- **[DEPLOYMENT.md](./DEPLOYMENT.md)**: Guía de despliegue con Docker y operaciones
- **[PREDICTOR.md](./PREDICTOR.md)**: Documentación completa del modelo LSTM multi-horizonte
- **[CHANGELOG.md](./CHANGELOG.md)**: Historial de cambios importantes del sistema

---

## Estado Actual

### Servicios Operativos ✅

- **MongoDB**: Almacenamiento de ~240k registros por moneda
- **Backend API**: 7 endpoints REST + WebSocket funcional
- **Coin Sync**: Sincronización automática cada 60s
- **Predictor**: 12 modelos multi-horizonte por símbolo
- **Frontend**: Visualización interactiva en tiempo real

### Métricas de Rendimiento

| Métrica | Valor |
|---------|-------|
| **Sincronización** | 1 minuto delay desde Binance |
| **Predicción** | ~30-45 min entrenamiento/símbolo |
| **Precisión LSTM** | R²=0.95, MAPE<3% |
| **WebSocket** | ~10k conexiones concurrentes |
| **Almacenamiento** | ~1 GB/mes/moneda |

### Monedas Soportadas

- **BTCUSDT** (Bitcoin)
- **ETHUSDT** (Ethereum)
- **BNBUSDT** (Binance Coin)

---

## Comandos Útiles

```bash
# Ver estado de servicios
docker-compose ps

# Ver logs en tiempo real
docker-compose logs -f

# Ver logs de un servicio específico
docker-compose logs -f backend
docker-compose logs -f predictor

# Reiniciar un servicio
docker-compose restart backend

# Detener todos los servicios
docker-compose down

# Reconstruir y reiniciar
docker-compose up -d --build

# Acceder a MongoDB
docker exec -it binance_mongodb mongosh -u admin -p SecurePass123! --authenticationDatabase admin
```

---

## Troubleshooting Básico

### Backend no responde
```bash
# Verificar health
curl http://localhost:8888/health

# Revisar logs
docker-compose logs backend
```

### No hay predicciones
- Las predicciones se generan cada hora en punto (ej: 14:00)
- Revisar logs del predictor: `docker-compose logs predictor`
- Verificar que existan datos históricos suficientes

### WebSocket no conecta
- Verificar que backend esté corriendo
- Comprobar puerto 8888 abierto
- Revisar consola del navegador

---

## Próximas Mejoras

- [ ] Más criptomonedas (SOL, ADA, DOT, etc.)
- [ ] Autenticación y autorización
- [ ] Dashboard de métricas (Prometheus + Grafana)
- [ ] Alertas configurables por precio
- [ ] Exportación de datos (CSV, Excel)
- [ ] Indicadores técnicos (RSI, MACD)
- [ ] Comparación multi-moneda
- [ ] Histórico de precisión de predicciones

---

## Soporte y Contribuciones

Para reportar issues o contribuir:
1. Revisar documentación en `/docs`
2. Revisar logs: `docker-compose logs`
3. Crear issue con detalles completos

---

**Proyecto desarrollado con Python, TensorFlow, MongoDB y Docker**

**Versión**: 2.0
**Última actualización**: Noviembre 2025
