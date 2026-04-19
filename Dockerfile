# Stage 1: build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: runtime
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/home/joi/.local/bin:$PATH

RUN apt-get update && apt-get install -y \
    libpq5 \
    ffmpeg \
    espeak \
    libespeak1 \
 && rm -rf /var/lib/apt/lists/* \
 && adduser --disabled-password --gecos '' joi

COPY --from=builder /root/.local /home/joi/.local

# Copy application code (deps already installed — this layer changes more often)
COPY --chown=joi:joi . .

USER joi

EXPOSE 8000

# Healthcheck delegated to docker-compose; kept here as a fallback
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
