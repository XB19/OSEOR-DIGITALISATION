FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# build-essential/libpq-dev : filet de sécurité si un paquet (cryptography...)
# doit être compilé en l'absence de roue précompilée pour cette plateforme.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000 8001

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "serve_api.py"]
