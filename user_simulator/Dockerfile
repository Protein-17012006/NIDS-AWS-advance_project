FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY main.py /app/

RUN pip install --no-cache-dir requests

CMD ["python", "-u", "main.py"]
