#!/bin/bash

# Script para compilar el frontend Angular y copiarlo a htdocs
# Uso: ./build-frontend.sh

set -e  # Salir si hay error

echo "========================================"
echo "  Build y Deploy del Frontend Angular"
echo "========================================"
echo ""

# Verificar que existe el directorio frontend
if [ ! -d "frontend" ]; then
    echo "ERROR: No se encuentra el directorio frontend"
    exit 1
fi

# Cambiar al directorio frontend
cd frontend

# Verificar que existen node_modules
if [ ! -d "node_modules" ]; then
    echo "Instalando dependencias de npm..."
    npm install
fi

# Compilar el frontend en modo producción
echo ""
echo "Compilando frontend en modo producción..."
npm run build

# Volver al directorio raíz
cd ..

# Crear directorio htdocs si no existe
if [ ! -d "htdocs" ]; then
    echo "Creando directorio htdocs..."
    mkdir -p htdocs
fi

# Limpiar htdocs
echo ""
echo "Limpiando directorio htdocs..."
rm -rf htdocs/*

# Copiar archivos compilados a htdocs
echo ""
echo "Copiando archivos compilados a htdocs..."
cp -r frontend/dist/binance-crypto-frontend/browser/* htdocs/

echo ""
echo "========================================"
echo "  Build completado exitosamente!"
echo "========================================"
echo ""
echo "Los archivos están en: htdocs/"
echo "Puedes levantar el frontend con: docker-compose up -d frontend"
echo "El frontend estará disponible en: http://localhost:8080"
echo ""

exit 0
