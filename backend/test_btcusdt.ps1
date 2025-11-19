# Script de prueba para BTCUSDT en PowerShell
# Este script verifica el funcionamiento del backend con Bitcoin

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Prueba de Backend Binance - BTCUSDT" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# URL base del API
$API_URL = "http://localhost:8888"

Write-Host "1. Verificando el estado del servicio..." -ForegroundColor Yellow
try {
    $healthResponse = Invoke-RestMethod -Uri "$API_URL/health" -Method Get
    Write-Host "   Respuesta:" -ForegroundColor White
    $healthResponse | ConvertTo-Json

    if ($healthResponse.status -eq "healthy") {
        Write-Host "   ✓ Servicio funcionando correctamente" -ForegroundColor Green
    } else {
        Write-Host "   ✗ Error: El servicio no está disponible" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "   ✗ Error: No se puede conectar al servicio" -ForegroundColor Red
    Write-Host "   Asegúrate de que Docker Compose esté corriendo: docker-compose up" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "2. Sincronizando datos de BTCUSDT..." -ForegroundColor Yellow
try {
    $body = @{
        symbol = "BTCUSDT"
    } | ConvertTo-Json

    $syncResponse = Invoke-RestMethod -Uri "$API_URL/api/sync" -Method Post -Body $body -ContentType "application/json"
    Write-Host "   Respuesta:" -ForegroundColor White
    $syncResponse | ConvertTo-Json -Depth 10

    if ($syncResponse.success) {
        Write-Host "   ✓ Sincronización completada" -ForegroundColor Green
        Write-Host "   Nuevos registros: $($syncResponse.new_records)" -ForegroundColor White
    } else {
        Write-Host "   ✗ Error en la sincronización" -ForegroundColor Red
    }
} catch {
    Write-Host "   ✗ Error al sincronizar: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "3. Obteniendo estadísticas de BTCUSDT..." -ForegroundColor Yellow
try {
    $statsResponse = Invoke-RestMethod -Uri "$API_URL/api/stats/BTCUSDT" -Method Get
    Write-Host "   Respuesta:" -ForegroundColor White
    $statsResponse | ConvertTo-Json -Depth 10
} catch {
    Write-Host "   ✗ Error al obtener estadísticas: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "4. Obteniendo los primeros 10 registros de BTCUSDT..." -ForegroundColor Yellow
try {
    $dataResponse = Invoke-RestMethod -Uri "$API_URL/api/data/BTCUSDT?limit=10" -Method Get
    Write-Host "   Cantidad de registros obtenidos: $($dataResponse.count)" -ForegroundColor White

    if ($dataResponse.count -gt 0) {
        Write-Host "   Primer registro:" -ForegroundColor White
        $dataResponse.data[0] | ConvertTo-Json
    }
} catch {
    Write-Host "   ✗ Error al obtener datos: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Prueba completada" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
