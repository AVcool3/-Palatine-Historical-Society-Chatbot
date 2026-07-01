# Container image for the Palatine History Chatbot.
# Works on Render, Fly.io, Railway, a VPS, or anywhere that runs Docker.
FROM python:3.11-slim

# System libs for Pillow (image handling) — small and safe defaults.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-build the search index from the seeded records.
RUN python -m src.ingest

ENV PORT=8080
EXPOSE 8080

# Honor the platform's $PORT if provided; default 8080 locally.
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 120 --preload"]
