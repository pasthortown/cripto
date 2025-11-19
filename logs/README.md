# Directorio de Logs

Este directorio contiene los archivos de log generados por el backend de Binance.

## Tipos de Archivos de Log

Los logs se generan automáticamente en formato `.txt` con rotación automática:

### 1. `app_YYYY-MM-DD.txt`
**Archivo de log general de la aplicación**
- Contiene todos los logs de nivel INFO, WARNING, ERROR y CRITICAL
- Incluye logs de todos los módulos (main, handlers, db_client, binance_client)
- Rotación automática: máximo 10 MB por archivo, mantiene 5 backups
- Se crea un nuevo archivo cada día

**Ejemplo de contenido:**
```
2025-11-13 10:30:15 - main - INFO - [main.py:22] - Sistema de logging configurado correctamente
2025-11-13 10:30:16 - db_client - INFO - [db_client.py:54] - Conectado exitosamente a MongoDB
2025-11-13 10:30:17 - main - INFO - [main.py:106] - Servidor Tornado iniciado en puerto 8888
```

### 2. `errors_YYYY-MM-DD.txt`
**Archivo exclusivo de errores**
- Contiene solo logs de nivel ERROR y CRITICAL
- Útil para debugging y análisis de problemas
- Rotación automática: máximo 10 MB por archivo, mantiene 5 backups
- Se crea un nuevo archivo cada día

**Ejemplo de contenido:**
```
2025-11-13 10:35:42 - handlers - ERROR - [handlers.py:124] - Error en sincronización: Connection timeout
2025-11-13 10:36:15 - db_client - ERROR - [db_client.py:89] - Error al insertar klines: Duplicate key error
```

### 3. `requests_YYYY-MM-DD.txt`
**Archivo de requests HTTP**
- Contiene logs de requests procesados por Tornado
- Incluye información de endpoints, métodos HTTP, códigos de respuesta
- Rotación automática: máximo 10 MB por archivo, mantiene 5 backups
- Se crea un nuevo archivo cada día

**Ejemplo de contenido:**
```
2025-11-13 10:40:00 - tornado.access - INFO - [web.py:2265] - 200 POST /api/sync (192.168.31.1) 1250.23ms
2025-11-13 10:40:05 - tornado.access - INFO - [web.py:2265] - 200 GET /api/stats/BTCUSDT (192.168.31.1) 15.67ms
```

## Características del Sistema de Logging

### Rotación Automática
- **Tamaño máximo**: 10 MB por archivo
- **Backups**: Se mantienen 5 versiones anteriores
- **Nomenclatura de backups**: `app_2025-11-13.txt.1`, `app_2025-11-13.txt.2`, etc.

### Niveles de Log

| Nivel | Descripción | Se guarda en |
|-------|-------------|--------------|
| DEBUG | Información detallada para debugging | app_*.txt |
| INFO | Información general del funcionamiento | app_*.txt, requests_*.txt |
| WARNING | Advertencias que no detienen la ejecución | app_*.txt |
| ERROR | Errores que afectan funcionalidad | app_*.txt, errors_*.txt |
| CRITICAL | Errores críticos del sistema | app_*.txt, errors_*.txt |

### Formato de Log

```
YYYY-MM-DD HH:MM:SS - módulo - NIVEL - [archivo.py:línea] - mensaje
```

**Ejemplo:**
```
2025-11-13 10:30:15 - handlers - INFO - [handlers.py:75] - Sincronizando datos de BTCUSDT
```

## Ubicación y Acceso

### En Docker
- **Ruta interna**: `/logs/`
- **Volumen**: Mapeado a `./logs` en el host
- Los logs se escriben en tiempo real desde el contenedor

### En el Host
- **Ruta**: `D:\Proyectos\binance\logs\`
- Los archivos son accesibles directamente desde Windows
- Se pueden abrir con cualquier editor de texto

## Monitoreo de Logs

### Ver logs en tiempo real (Linux/Mac)
```bash
# Todos los logs de hoy
tail -f logs/app_$(date +%Y-%m-%d).txt

# Solo errores
tail -f logs/errors_$(date +%Y-%m-%d).txt

# Requests HTTP
tail -f logs/requests_$(date +%Y-%m-%d).txt
```

### Ver logs en tiempo real (Windows PowerShell)
```powershell
# Todos los logs de hoy
Get-Content "logs\app_$(Get-Date -Format 'yyyy-MM-dd').txt" -Wait

# Solo errores
Get-Content "logs\errors_$(Get-Date -Format 'yyyy-MM-dd').txt" -Wait
```

### Buscar en logs
```bash
# Buscar errores específicos
grep "Connection" logs/errors_*.txt

# Buscar requests a un endpoint
grep "/api/sync" logs/requests_*.txt

# Buscar por símbolo
grep "BTCUSDT" logs/app_*.txt
```

## Mantenimiento

### Limpieza Manual
Los logs antiguos se pueden eliminar manualmente:

```bash
# Eliminar logs de hace más de 7 días (Linux/Mac)
find logs/ -name "*.txt*" -mtime +7 -delete

# Windows PowerShell
Get-ChildItem logs\*.txt* | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item
```

### Espacio en Disco
- Cada archivo puede crecer hasta 10 MB
- Con 5 backups por tipo y 3 tipos de archivo = máximo ~150 MB por día
- Monitorear el espacio periódicamente

## Troubleshooting

### Problema: No se generan logs
```bash
# Verificar permisos del directorio
ls -la logs/

# Verificar variable de entorno en Docker
docker-compose exec backend env | grep LOG_DIR

# Verificar logs de Docker
docker-compose logs backend
```

### Problema: Archivos de log muy grandes
```bash
# Verificar tamaño actual
du -sh logs/

# Los archivos deberían rotar automáticamente a 10 MB
# Si no rotan, verificar logger_config.py
```

### Problema: No se pueden leer los logs
```bash
# En Windows, asegurarse de tener permisos
# Abrir PowerShell como administrador si es necesario

# Verificar codificación (deben ser UTF-8)
file logs/app_*.txt
```

## Análisis de Logs

### Estadísticas de Requests
```bash
# Contar requests por endpoint
grep "POST /api/sync" logs/requests_*.txt | wc -l

# Requests más lentos
grep "ms$" logs/requests_*.txt | sort -t'(' -k2 -rn | head -10
```

### Análisis de Errores
```bash
# Tipos de errores más comunes
grep ERROR logs/errors_*.txt | cut -d':' -f2 | sort | uniq -c | sort -rn

# Errores en las últimas 24 horas
grep "$(date +%Y-%m-%d)" logs/errors_*.txt
```

## Configuración

La configuración de logging se encuentra en:
- **Módulo**: `backend/app/logger_config.py`
- **Config**: `backend/app/config.py` (variable `LOG_DIR` y `LOG_LEVEL`)

Para cambiar el nivel de logging, modificar en `.env`:
```env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Integración con Herramientas

### Logrotate (Linux)
Si se ejecuta en Linux, se puede usar logrotate:

```bash
# /etc/logrotate.d/binance
/path/to/logs/*.txt {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### Monitoreo con ELK Stack
Los logs en formato texto se pueden integrar con:
- **Filebeat**: Para recolección
- **Logstash**: Para procesamiento
- **Elasticsearch**: Para almacenamiento
- **Kibana**: Para visualización

## Notas Importantes

1. Los archivos `.txt` están en `.gitignore` y no se suben a git
2. La carpeta `logs/` se mantiene en git con `.gitkeep`
3. Los logs se escriben en UTF-8
4. Incluyen timestamp en zona horaria UTC
5. La rotación es automática, no requiere intervención manual
