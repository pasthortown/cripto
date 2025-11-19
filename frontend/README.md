# Binance Crypto Frontend - Angular 17

Frontend web para el sistema de análisis y predicción de criptomonedas en tiempo real.

## Características

- **Chart Interactivo** con Chart.js mostrando precios reales y predicciones
- **Actualización en Tiempo Real** vía WebSocket
- **Selector de Monedas** dinámico (BTCUSDT, ETHUSDT, BNBUSDT)
- **Rangos de Tiempo** configurables (15min, 30min, 1h, día, semana, mes, año)
- **Interfaz Responsiva** adaptable a móviles y escritorio
- **Indicadores de Estado** para conexión WebSocket y última actualización

## Tecnologías

- **Angular 17** (Standalone Components)
- **TypeScript 5.2**
- **Chart.js 4.4** para visualización de datos
- **RxJS** para manejo de observables
- **WebSocket** para comunicación en tiempo real

## Requisitos Previos

- **Node.js** 18+ y npm
- **Backend** corriendo en http://localhost:8888

## Instalación

### 1. Instalar Dependencias

```bash
cd frontend
npm install
```

### 2. Verificar Conexión al Backend

Asegúrate de que el backend esté corriendo:

```bash
# Verificar health check
curl http://localhost:8888/health
```

## Ejecución

### Modo Desarrollo

```bash
npm start
```

La aplicación estará disponible en: **http://localhost:4200**

### Modo Producción

```bash
# Build para producción
npm run build

# Los archivos compilados estarán en dist/
```

## Estructura del Proyecto

```
frontend/
├── src/
│   ├── app/
│   │   ├── components/
│   │   │   └── crypto-chart/          # Componente principal del chart
│   │   │       ├── crypto-chart.component.ts
│   │   │       ├── crypto-chart.component.html
│   │   │       └── crypto-chart.component.css
│   │   ├── services/
│   │   │   └── binance-api.service.ts  # Servicio API + WebSocket
│   │   ├── models/
│   │   │   └── crypto.models.ts        # Interfaces TypeScript
│   │   ├── app.component.ts
│   │   ├── app.config.ts
│   │   └── app.routes.ts
│   ├── index.html
│   ├── main.ts
│   └── styles.css
├── angular.json
├── package.json
├── tsconfig.json
└── README.md
```

## Uso de la Aplicación

### 1. Seleccionar Moneda

Usa el dropdown "Moneda" para cambiar entre las criptomonedas disponibles:
- BTCUSDT
- ETHUSDT
- BNBUSDT

### 2. Seleccionar Rango de Tiempo

Usa el dropdown "Rango de Tiempo" para ajustar la ventana de visualización:
- **15 Minutos**: Últimos 15 minutos
- **30 Minutos**: Últimos 30 minutos
- **1 Hora**: Última hora
- **Día**: Últimas 24 horas (por defecto)
- **Semana**: Última semana
- **Mes**: Último mes
- **Año**: Último año

### 3. Actualización Automática

El chart se actualiza automáticamente cuando:
- El servicio `coin_sync` sincroniza nuevos datos cada minuto
- El WebSocket notifica que hay nuevos datos disponibles
- Se eliminan los datos más antiguos y se agregan los más nuevos (ventana deslizante)

### 4. Actualización Manual

Click en el botón **"🔄 Actualizar"** para forzar una recarga de datos.

## Interpretación del Chart

### Línea Azul Sólida
- **Precio Real** de la criptomoneda
- Datos obtenidos de Binance API
- Actualizado cada minuto

### Línea Roja Punteada
- **Predicción** generada por el modelo Bi-LSTM
- Predicciones del día actual (00:00 a 23:59)
- Generadas automáticamente a las 00:00:01

### Panel de Información

Muestra:
- **Datos Históricos**: Cantidad de registros cargados
- **Predicciones**: Cantidad de predicciones disponibles
- **Último Precio**: Precio más reciente de la moneda
- **Última Predicción**: Predicción más reciente disponible

### Indicadores de Estado

- **🟢 Conectado**: WebSocket conectado y recibiendo actualizaciones
- **🔴 Desconectado**: WebSocket desconectado (intentando reconectar)
- **Última actualización**: Timestamp de la última sincronización

## API del Backend Utilizada

### REST Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/symbols` | GET | Lista de monedas disponibles |
| `/api/data/{symbol}` | GET | Datos históricos |
| `/api/predictions/{symbol}` | GET | Predicciones del día |
| `/api/stats/{symbol}` | GET | Estadísticas de la moneda |

### WebSocket

**URL**: `ws://localhost:8888/ws/updates`

**Mensajes del Cliente**:
```json
{
  "action": "subscribe",
  "symbols": ["BTCUSDT"]
}
```

**Mensajes del Servidor**:
```json
{
  "type": "sync_complete",
  "symbol": "BTCUSDT",
  "timestamp": "2025-11-17T14:45:00Z",
  "statistics": {
    "new_records": 1,
    "total_records": 244238,
    "last_price": 94874.0
  }
}
```

## Configuración

### Cambiar URL del Backend

Edita `src/app/services/binance-api.service.ts`:

```typescript
private readonly BASE_URL = 'http://localhost:8888';
private readonly WS_URL = 'ws://localhost:8888/ws/updates';
```

### Cambiar Puerto del Frontend

Edita `angular.json`:

```json
"serve": {
  "options": {
    "port": 4200,  // Cambia este valor
    "host": "localhost"
  }
}
```

## Troubleshooting

### Error: Backend no responde

**Síntoma**: La aplicación muestra "Error al cargar datos"

**Solución**:
1. Verifica que el backend esté corriendo: `curl http://localhost:8888/health`
2. Verifica que Docker containers estén up: `docker-compose ps`
3. Revisa logs del backend: `docker-compose logs backend`

### Error: WebSocket no conecta

**Síntoma**: Indicador muestra "Desconectado"

**Solución**:
1. Verifica que el backend permita conexiones WebSocket
2. Revisa la consola del navegador para errores
3. Verifica que no haya firewalls bloqueando el puerto 8888

### Error: No hay predicciones

**Síntoma**: La línea de predicción no se muestra

**Solución**:
1. Las predicciones se generan a las 00:00:01 cada día
2. Verifica que el servicio `predictor` esté corriendo: `docker-compose ps`
3. Revisa logs del predictor: `docker-compose logs predictor`
4. Verifica que haya predicciones en MongoDB:
   ```bash
   docker exec binance_mongodb mongosh -u admin -p SecurePass123! \
     --authenticationDatabase admin binance_data \
     --eval "db.prediccion_btcusdt.countDocuments({})"
   ```

### Error: Datos no se actualizan

**Síntoma**: El chart no se actualiza automáticamente

**Solución**:
1. Verifica que `coin_sync` esté corriendo: `docker-compose ps`
2. Revisa logs de coin_sync: `docker-compose logs coin_sync`
3. Verifica conexión WebSocket en el indicador de estado
4. Recarga la página (F5)

## Performance

### Optimizaciones Implementadas

- **Actualización del Chart sin animación**: `chart.update('none')`
- **Ventana deslizante**: Solo mantiene datos del rango seleccionado
- **Debouncing de WebSocket**: Evita múltiples actualizaciones simultáneas
- **Lazy loading**: Carga de datos bajo demanda

### Recomendaciones

- Para mejor performance, usa rangos de tiempo más cortos (15min, 30min)
- El navegador puede limitar conexiones WebSocket simultáneas
- Cierra otras pestañas que consuman WebSockets

## Build para Producción

```bash
# Build optimizado
npm run build

# Los archivos estarán en dist/binance-crypto-frontend/

# Servir con un servidor estático
cd dist/binance-crypto-frontend
npx http-server -p 8080
```

## Características Futuras

- [ ] Modo oscuro
- [ ] Indicadores técnicos (RSI, MACD, Bollinger Bands)
- [ ] Comparación de múltiples monedas
- [ ] Exportación de datos a CSV/Excel
- [ ] Alertas de precio personalizables
- [ ] Histórico de precisión de predicciones
- [ ] Gráficos adicionales (volumen, trades)

## Contribuir

Para contribuir al proyecto:

1. Fork el repositorio
2. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
3. Commit cambios: `git commit -am 'Agregar nueva funcionalidad'`
4. Push a la rama: `git push origin feature/nueva-funcionalidad`
5. Crea un Pull Request

## Licencia

Este proyecto es parte del sistema de análisis de criptomonedas Binance.

## Contacto

Para reportar issues o sugerencias, por favor crea un issue en el repositorio.

---

**Versión**: 1.0.0
**Fecha**: 2025-11-17
**Autor**: Sistema Binance Analysis & Prediction
