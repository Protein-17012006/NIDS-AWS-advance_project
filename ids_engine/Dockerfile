FROM python:3.10-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements-inference.txt .
RUN pip install --no-cache-dir -r requirements-inference.txt

# Application code
COPY ids_engine/ ./ids_engine/

# Model weights directory (mounted or downloaded from S3 at runtime)
RUN mkdir -p /app/models

ENV IDS_MODEL_DIR=/app/models
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "ids_engine.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
