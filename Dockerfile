# Usar una imagen base oficial de Python
FROM python:3.11-slim

# Instalar FFmpeg, una dependencia del sistema necesaria para procesar audio
RUN apt-get update && apt-get install -y ffmpeg

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar el archivo de requerimientos e instalar las librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Comando para ejecutar la aplicación usando Gunicorn (servidor de producción)
# Cloud Run asignará el puerto a través de la variable de entorno $PORT
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
