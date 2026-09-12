FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends v4l-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server.py /app/server.py

CMD ["python", "-u", "-X", "faulthandler", "/app/server.py"]
