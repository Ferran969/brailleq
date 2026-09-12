FROM python:3.13-slim-bookworm

RUN python -m pip install --no-cache-dir --upgrade pip

RUN python -m pip install --no-cache-dir \
    paddlepaddle==3.2.1 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

RUN python -m pip install --no-cache-dir \
    paddleocr \
    flask

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server.py /app/server.py

EXPOSE 5000

CMD ["python", "-u", "-X", "faulthandler", "/app/server.py"]