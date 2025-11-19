# Deployment Guide - Binance Crypto Predictor

**Guía completa de despliegue con Docker**

Versión: 2.0

---

## Prerrequisitos

- Docker 20.10+ y Docker Compose 2.0+
- 16 GB RAM mínimo recomendado
- 50 GB espacio en disco
- Puertos disponibles: 8888, 21018, 8080

---

## Configuración Inicial

### 1. Clonar Repositorio

```bash
git clone <repo-url>
cd binance
```

### 2. Configurar Variables de Entorno

```bash
cp .env.example .env
```

Editar `.env`:

```env
# MongoDB
MONGODB_ROOT_USERNAME=admin
MONGODB_ROOT_PASSWORD=SecurePass123!  # CAMBIAR EN PRODUCCIÓN
MONGODB_DATABASE=binance_data
MONGODB_PORT=21018

# Backend
SERVER_PORT=8888
LOG_LEVEL=INFO

# Coin Sync
SYNC_INTERVAL_SECONDS=60

# Predictor (Multi-Horizonte)
MODEL_MAX_AGE_DAYS=1
LSTM_UNITS=128
LSTM_LAYERS=2
DROPOUT_RATE=0.2
EPOCHS=100
BATCH_SIZE=32
SEQUENCE_LENGTH=1440
VALIDATION_SPLIT=0.2

# Network IPs
MONGODB_IP=192.168.31.10
BACKEND_IP=192.168.31.11
COIN_SYNC_IP=192.168.31.12
PREDICTOR_IP=192.168.31.13
FRONTEND_IP=192.168.31.14
```

---

## Despliegue

### 1. Construir e Iniciar Servicios

```bash
docker-compose up -d --build
```

### 2. Verificar Estado

```bash
docker-compose ps
```

Salida esperada:
```
NAME                   STATUS              PORTS
binance_mongodb        Up (healthy)        0.0.0.0:21018->27017/tcp
binance_backend        Up (healthy)        0.0.0.0:8888->8888/tcp
binance_coin_sync      Up
binance_predictor      Up
binance_frontend       Up (healthy)        0.0.0.0:8080->80/tcp
```

### 3. Ver Logs

```bash
# Todos los servicios
docker-compose logs -f

# Backend
docker-compose logs -f backend

# Predictor
docker-compose logs -f predictor

# Coin Sync
docker-compose logs -f coin_sync
```

---

## Verificación

### 1. Health Check Backend

```bash
curl http://localhost:8888/health
```

Respuesta esperada:
```json
{
  "status": "healthy",
  "service": "binance-backend",
  "database": "connected"
}
```

### 2. Verificar Símbolos Disponibles

```bash
curl http://localhost:8888/api/symbols
```

### 3. Acceder al Frontend

Abrir navegador: http://localhost:8080

---

## Operaciones Comunes

### Reiniciar un Servicio

```bash
docker-compose restart backend
docker-compose restart predictor
```

### Detener Servicios

```bash
# Detener sin eliminar contenedores
docker-compose stop

# Detener y eliminar contenedores (datos persisten)
docker-compose down

# ELIMINAR TODO (incluye datos)
docker-compose down -v
```

### Reconstruir Imagen

```bash
# Reconstruir backend
docker-compose build --no-cache backend

# Reconstruir predictor
docker-compose build --no-cache predictor
```

### Ver Logs de Error

```bash
# Archivos de log en host
tail -f logs/backend_$(date +%Y-%m-%d).txt
tail -f logs/predictor_errors_$(date +%Y-%m-%d).txt
```

---

## Acceso a MongoDB

```bash
# Desde container
docker exec -it binance_mongodb mongosh -u admin -p SecurePass123! --authenticationDatabase admin

# Desde host (si tienes mongosh instalado)
mongosh "mongodb://admin:SecurePass123!@localhost:21018/?authSource=admin"

# Comandos útiles en mongosh
use binance_data
show collections
db.klines_btcusdt.countDocuments()
db.prediccion_btcusdt.find().limit(5)
```

---

## Troubleshooting

### Container se reinicia continuamente

```bash
# Ver logs
docker-compose logs --tail=100 predictor

# Ver código de salida
docker inspect binance_predictor | grep -A 5 "State"

# Código 137 = OOM (Out of Memory)
# Código 1 = Error general
```

### Puerto ya en uso

```bash
# Windows
netstat -ano | findstr :8888

# Linux/Mac
lsof -i :8888

# Cambiar puerto en .env
SERVER_PORT=8889
```

### MongoDB no conecta

```bash
# Verificar que MongoDB esté corriendo
docker-compose ps mongodb

# Ver logs
docker-compose logs mongodb

# Recrear volúmenes (ELIMINA DATOS)
docker-compose down -v
docker-compose up -d --build
```

---

## Backup y Restauración

### Backup de MongoDB

```bash
# Crear backup
docker exec binance_mongodb mongodump \
  -u admin \
  -p SecurePass123! \
  --authenticationDatabase admin \
  -d binance_data \
  -o /data/backup

# Copiar a host
docker cp binance_mongodb:/data/backup ./backup_$(date +%Y%m%d)
```

### Restaurar Backup

```bash
# Copiar backup al container
docker cp ./backup_20251117 binance_mongodb:/data/backup

# Restaurar
docker exec binance_mongodb mongorestore \
  -u admin \
  -p SecurePass123! \
  --authenticationDatabase admin \
  -d binance_data \
  /data/backup/binance_data
```

---

## Actualización del Sistema

### 1. Detener Servicios

```bash
docker-compose down
```

### 2. Actualizar Código

```bash
git pull origin main
```

### 3. Reconstruir y Reiniciar

```bash
docker-compose up -d --build
```

---

## Monitoreo

### Ver Uso de Recursos

```bash
docker stats
```

### Verificar Espacio en Disco

```bash
# Volúmenes
docker system df -v

# Logs
du -sh logs/
```

### Limpiar Sistema

```bash
# Eliminar containers detenidos
docker container prune

# Eliminar imágenes sin usar
docker image prune

# Eliminar todo (CUIDADO)
docker system prune -a
```

---

## Producción

### Recomendaciones

1. **Cambiar contraseña de MongoDB** en `.env`
2. **Habilitar SSL/TLS** para conexiones externas
3. **Configurar firewall** para limitar acceso
4. **Implementar backup automático** (cron job)
5. **Monitoreo con Prometheus + Grafana**
6. **Logs centralizados** (ELK Stack)

### Configuración de Firewall (ejemplo)

```bash
# Permitir solo desde IPs específicas
ufw allow from 10.0.0.0/24 to any port 8888
ufw allow from 10.0.0.0/24 to any port 21018
```

---

**Documentación actualizada**: Noviembre 2025
