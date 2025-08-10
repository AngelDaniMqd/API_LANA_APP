FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY start.sh .
RUN chmod +x start.sh

# Exponer el puerto dinámicamente
ENV PORT=8000
EXPOSE ${PORT}

CMD ["./start.sh"]