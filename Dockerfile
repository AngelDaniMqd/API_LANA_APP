FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de la aplicación
COPY . .

# Asegurar permisos del script de inicio
COPY start.sh .
RUN chmod +x start.sh

# Variables de entorno por defecto
ENV PORT=8000
ENV WORKERS=1
ENV TIMEOUT=75

# Comando de inicio
CMD ["./start.sh"]