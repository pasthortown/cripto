#!/bin/bash

# Script de prueba para BTCUSDT
# Este script verifica el funcionamiento del backend con Bitcoin

echo "========================================="
echo "Prueba de Backend Binance - BTCUSDT"
echo "========================================="
echo ""

# URL base del API
API_URL="http://localhost:8888"

echo "1. Verificando el estado del servicio..."
HEALTH_RESPONSE=$(curl -s "${API_URL}/health")
echo "   Respuesta: ${HEALTH_RESPONSE}"
echo ""

# Verificar si el servicio está healthy
if echo "${HEALTH_RESPONSE}" | grep -q "healthy"; then
    echo "   ✓ Servicio funcionando correctamente"
else
    echo "   ✗ Error: El servicio no está disponible"
    exit 1
fi

echo ""
echo "2. Sincronizando datos de BTCUSDT..."
SYNC_RESPONSE=$(curl -s -X POST "${API_URL}/api/sync" \
    -H "Content-Type: application/json" \
    -d '{"symbol": "BTCUSDT"}')

echo "   Respuesta:"
echo "${SYNC_RESPONSE}" | python3 -m json.tool 2>/dev/null || echo "${SYNC_RESPONSE}"
echo ""

# Verificar si la sincronización fue exitosa
if echo "${SYNC_RESPONSE}" | grep -q "success"; then
    echo "   ✓ Sincronización completada"
else
    echo "   ✗ Error en la sincronización"
fi

echo ""
echo "3. Obteniendo estadísticas de BTCUSDT..."
STATS_RESPONSE=$(curl -s "${API_URL}/api/stats/BTCUSDT")
echo "   Respuesta:"
echo "${STATS_RESPONSE}" | python3 -m json.tool 2>/dev/null || echo "${STATS_RESPONSE}"
echo ""

echo ""
echo "4. Obteniendo los primeros 10 registros de BTCUSDT..."
DATA_RESPONSE=$(curl -s "${API_URL}/api/data/BTCUSDT?limit=10")
echo "   Cantidad de registros obtenidos:"
echo "${DATA_RESPONSE}" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f\"   {data.get('count', 0)} registros\")" 2>/dev/null || echo "   Error al parsear respuesta"
echo ""

echo "========================================="
echo "Prueba completada"
echo "========================================="
