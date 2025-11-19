# Usar imagen base de Python 3.11
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY app/ ./app/

# Exponer el puerto 8888
EXPOSE 8888

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV SERVER_PORT=8888
ENV MONGODB_HOST=mongodb
ENV MONGODB_PORT=27017
ENV MONGODB_DATABASE=binance_data

# Comando para ejecutar la aplicación
CMD ["python", "app/main.py"]
