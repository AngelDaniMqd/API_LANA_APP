FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .
COPY start.sh .
RUN chmod +x start.sh

# Variables de entorno para timeouts
ENV UVICORN_TIMEOUT=300
ENV PORT=8000

# Ejecutar script de inicio
CMD ["./start.sh"]