FROM python:3.12-slim

WORKDIR /app

# Copiar requirements.txt primero para aprovechar el cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Puerto que usará la aplicación
EXPOSE 8000

# Comando para ejecutar la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]