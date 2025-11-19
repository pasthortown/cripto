# Dockerfile para el servicio de predicción con LSTM
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Crear directorio para modelos
RUN mkdir -p /app/models

# Comando para ejecutar la aplicación
CMD ["python", "main.py"]
