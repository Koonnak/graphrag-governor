FROM python:3.11-slim

# System deps (faiss/torch often need libgomp1)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git ca-certificates libgomp1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# App
RUN useradd -m -u 1000 appuser
COPY . /app
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Healthcheck on FastAPI /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

# Production server (Gunicorn + Uvicorn workers)
CMD ["gunicorn","src.api.main:app","-k","uvicorn.workers.UvicornWorker","--workers","2","--bind","0.0.0.0:8000","--timeout","120"]
