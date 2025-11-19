# Usar imagen base de Python 3.11
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del servicio
COPY *.py ./

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV BACKEND_URL=http://backend:8888
ENV SYNC_INTERVAL_SECONDS=60
ENV HTTP_TIMEOUT=300

# Comando para ejecutar el servicio
CMD ["python", "main.py"]
