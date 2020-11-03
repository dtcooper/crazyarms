FROM python:3.9-alpine

RUN apk add --no-cache --virtual .build-deps gcc musl-dev

RUN mkdir /app
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

RUN apk del .build-deps gcc musl-dev

COPY sse.py /app/
CMD gunicorn --worker-class aiohttp.GunicornWebWorker -b 0.0.0.0:3000 --graceful-timeout 2 --capture-output --access-logfile - sse
