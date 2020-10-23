FROM python:3.9

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# TODO: Remove for initial release / development only
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        netcat \
        telnet \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir ipdb ipython

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        exiftool \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /app
WORKDIR /app
COPY app/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

RUN curl -sLo /usr/local/bin/wait-for-it https://raw.githubusercontent.com/vishnubob/wait-for-it/81b1373f/wait-for-it.sh \
    && chmod +x /usr/local/bin/wait-for-it

COPY app /app/
COPY image/ /

ENTRYPOINT ["/entrypoint.sh"]
CMD []
