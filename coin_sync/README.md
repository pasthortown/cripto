# Coin Sync - Servicio de Sincronización Automática

Servicio que sincroniza automáticamente todas las monedas disponibles cada minuto.

## Funcionalidad

1. **Al iniciar**:
   - Espera a que el backend esté disponible
   - Obtiene la lista de monedas desde `/api/symbols`
   - Sincroniza todas las monedas inmediatamente

2. **Cada minuto**:
   - Verifica que el backend esté disponible
   - Sincroniza todas las monedas automáticamente
   - Registra logs detallados de cada operación

## Características

- ✅ Sincronización automática cada 60 segundos (configurable)
- ✅ Reintentos automáticos en caso de error
- ✅ Logs detallados en archivos `.txt`
- ✅ Manejo de señales (SIGINT, SIGTERM) para shutdown limpio
- ✅ Health check del backend antes de sincronizar
- ✅ Compatible con Docker

## Configuración

### Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `BACKEND_URL` | URL del backend | http://backend:8888 |
| `SYNC_INTERVAL_SECONDS` | Intervalo entre sincronizaciones | 60 |
| `LOG_LEVEL` | Nivel de logging | INFO |
| `LOG_DIR` | Directorio de logs | /logs |
| `HTTP_TIMEOUT` | Timeout HTTP en segundos | 300 |
| `MAX_RETRIES` | Reintentos en caso de error | 3 |
| `RETRY_DELAY_SECONDS` | Delay entre reintentos | 10 |
| `SYMBOLS_TO_SYNC` | Lista de símbolos (vacío = todos) | "" |

## Logs Generados

### `coin_sync_YYYY-MM-DD.txt`
Log general del servicio de sincronización.

**Ejemplo:**
```
2025-11-13 23:45:00 - __main__ - INFO - [main.py:25] - SERVICIO DE SINCRONIZACIÓN AUTOMÁTICA
2025-11-13 23:45:01 - backend_client - INFO - [backend_client.py:32] - Cliente del backend inicializado
2025-11-13 23:45:05 - sync_service - INFO - [sync_service.py:85] - INICIO DE SINCRONIZACIÓN #1
2025-11-13 23:45:10 - backend_client - INFO - [backend_client.py:115] - ✓ BTCUSDT sincronizado: 5 nuevos registros
2025-11-13 23:45:15 - sync_service - INFO - [sync_service.py:120] - FIN DE SINCRONIZACIÓN #1
```

### `coin_sync_errors_YYYY-MM-DD.txt`
Solo errores del servicio.

## Uso

### Con Docker Compose
```bash
# Iniciar todos los servicios (incluyendo coin_sync)
docker-compose up -d

# Ver logs del servicio
docker-compose logs -f coin_sync

# Detener solo coin_sync
docker-compose stop coin_sync

# Reiniciar coin_sync
docker-compose restart coin_sync
```

### Local (Desarrollo)
```bash
# Instalar dependencias
cd coin_sync
pip install -r requirements.txt

# Configurar variables de entorno
export BACKEND_URL=http://localhost:8888
export SYNC_INTERVAL_SECONDS=60
export LOG_DIR=./logs

# Ejecutar
python main.py
```

## Estructura del Código

```
coin_sync/
├── main.py               # Punto de entrada
├── sync_service.py       # Lógica de sincronización
├── backend_client.py     # Cliente HTTP para el backend
├── logger_config.py      # Configuración de logging
├── config.py             # Configuración y variables
├── requirements.txt      # Dependencias
├── Dockerfile            # Imagen Docker
└── README.md             # Esta documentación
```

## Flujo de Trabajo

```
┌─────────────────────────────────────────┐
│         Inicio del Servicio             │
└─────────────────┬───────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Esperar Backend│
         │   (Health Check)│
         └────────┬────────┘
                  │ Backend OK
                  ▼
      ┌───────────────────────┐
      │ Obtener Lista Símbolos│
      │   (GET /api/symbols)   │
      └───────────┬───────────┘
                  │
                  ▼
      ┌───────────────────────┐
      │ Sincronización Inicial│
      │ (Todas las monedas)   │
      └───────────┬───────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Esperar 60s    │
         └────────┬────────┘
                  │
                  ▼
      ┌───────────────────────┐
      │ Health Check Backend  │
      └───────────┬───────────┘
                  │ OK
                  ▼
      ┌───────────────────────┐
      │ Sincronizar Monedas   │
      │ (POST /api/sync)      │
      └───────────┬───────────┘
                  │
                  └──────────┐
                             │ Loop infinito
                             └────────┐
                                      │
                          (Repetir cada 60s)
```

## Monitoreo

### Ver Estado del Servicio
```bash
# Estado del contenedor
docker-compose ps coin_sync

# Logs en tiempo real
docker-compose logs -f coin_sync

# Últimas 50 líneas
docker-compose logs --tail=50 coin_sync
```

### Ver Logs del Sistema
```bash
# Log general
tail -f logs/coin_sync_2025-11-13.txt

# Solo errores
tail -f logs/coin_sync_errors_2025-11-13.txt

# Buscar sincronizaciones
grep "INICIO DE SINCRONIZACIÓN" logs/coin_sync_*.txt
```

### Métricas
```bash
# Contar sincronizaciones realizadas
grep "FIN DE SINCRONIZACIÓN" logs/coin_sync_*.txt | wc -l

# Ver monedas sincronizadas
grep "sincronizado:" logs/coin_sync_*.txt
```

## Troubleshooting

### Problema: Servicio no inicia
```bash
# Verificar logs
docker-compose logs coin_sync

# Verificar que el backend esté disponible
docker-compose ps backend
curl http://localhost:8888/health
```

### Problema: No sincroniza ninguna moneda
```bash
# Verificar que haya monedas en la BD
curl http://localhost:8888/api/symbols

# Si no hay monedas, sincronizar manualmente una primero
curl -X POST http://localhost:8888/api/sync \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT"}'
```

### Problema: Errores de timeout
```bash
# Aumentar timeout en .env
SYNC_INTERVAL_SECONDS=120
HTTP_TIMEOUT=600

# Reiniciar servicio
docker-compose restart coin_sync
```

## Notas Importantes

1. **Primera ejecución**: Si no hay monedas en la BD, el servicio no tendrá nada que sincronizar. Primero sincroniza al menos una moneda manualmente.

2. **Intervalo**: El intervalo por defecto es 60 segundos. Puedes ajustarlo en el `.env`.

3. **Recursos**: Si hay muchas monedas, cada sincronización puede tomar varios minutos.

4. **Logs**: Los logs se comparten con el host en `./logs/`. Son accesibles incluso si el contenedor se detiene.

5. **Shutdown**: El servicio maneja señales de terminación (Ctrl+C, SIGTERM) de forma limpia.

## Integración con el Sistema

El servicio `coin_sync` complementa el backend:

- **Backend**: Expone endpoints REST para sincronización bajo demanda
- **Coin Sync**: Automatiza la sincronización periódica de todas las monedas
- **Frontend** (futuro): Puede mostrar estadísticas de sincronización

## Desarrollado con

- Python 3.11
- Requests (cliente HTTP)
- Docker
- Logging con rotación de archivos
