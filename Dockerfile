FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Script de inicio
COPY start.sh .
RUN chmod +x start.sh

# Puerto por defecto (se sobrescribirá con la variable PORT de Railway)
ENV PORT=8000

# Ejecutar script de inicio
CMD ["./start.sh"]