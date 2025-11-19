@echo off
REM Script para compilar el frontend Angular y copiarlo a htdocs
REM Uso: build-frontend.bat

echo ========================================
echo   Build y Deploy del Frontend Angular
echo ========================================
echo.

REM Verificar que existe el directorio frontend
if not exist "frontend" (
    echo ERROR: No se encuentra el directorio frontend
    exit /b 1
)

REM Cambiar al directorio frontend
cd frontend

REM Verificar que existen node_modules
if not exist "node_modules" (
    echo Instalando dependencias de npm...
    call npm install
    if errorlevel 1 (
        echo ERROR: Fallo la instalacion de dependencias
        cd ..
        exit /b 1
    )
)

REM Compilar el frontend en modo produccion
echo.
echo Compilando frontend en modo produccion...
call npm run build
if errorlevel 1 (
    echo ERROR: Fallo la compilacion del frontend
    cd ..
    exit /b 1
)

REM Volver al directorio raiz
cd ..

REM Crear directorio htdocs si no existe
if not exist "htdocs" (
    echo Creando directorio htdocs...
    mkdir htdocs
)

REM Limpiar htdocs
echo.
echo Limpiando directorio htdocs...
if exist "htdocs\*" (
    del /Q htdocs\*
    for /d %%p in (htdocs\*) do rmdir "%%p" /s /q
)

REM Copiar archivos compilados a htdocs
echo.
echo Copiando archivos compilados a htdocs...
xcopy /E /I /Y "frontend\dist\binance-crypto-frontend\browser\*" "htdocs\"
if errorlevel 1 (
    echo ERROR: Fallo la copia de archivos
    exit /b 1
)

echo.
echo ========================================
echo   Build completado exitosamente!
echo ========================================
echo.
echo Los archivos estan en: htdocs\
echo Puedes levantar el frontend con: docker-compose up -d frontend
echo El frontend estara disponible en: http://localhost:8080
echo.

exit /b 0
