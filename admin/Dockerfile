FROM python:3.9

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir /app
WORKDIR /app
COPY app/requirements.txt /app/
RUN pip install -r requirements.txt

RUN curl -sLo /usr/local/bin/dotenv https://raw.githubusercontent.com/bashup/dotenv/d71c9d78/dotenv \
    && curl -sLo /usr/local/bin/wait-for-it https://raw.githubusercontent.com/vishnubob/wait-for-it/81b1373f/wait-for-it.sh \
    && chmod +x /usr/local/bin/dotenv /usr/local/bin/wait-for-it

COPY app /app/
COPY image/ /

ENTRYPOINT ["/entrypoint.sh"]
CMD []
