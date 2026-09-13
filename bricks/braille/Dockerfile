FROM python:3.13-slim-trixie

RUN python -m pip install --no-cache-dir flask

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        liblouis-bin \
        liblouis-data \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY server.py .

EXPOSE 8080

CMD ["python", "-u", "server.py"]
