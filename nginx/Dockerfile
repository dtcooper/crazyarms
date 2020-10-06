FROM library/nginx

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        certbot \
        python-certbot-nginx \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install j2cli

RUN curl -sLo /usr/local/bin/dotenv https://raw.githubusercontent.com/bashup/dotenv/d71c9d78/dotenv \
    && curl -sLo /usr/local/bin/wait-for-it https://raw.githubusercontent.com/vishnubob/wait-for-it/81b1373f/wait-for-it.sh \
    && chmod +x /usr/local/bin/dotenv /usr/local/bin/wait-for-it

COPY image/ /
