FROM library/nginx:alpine

RUN apk add --no-cache \
    certbot \
    certbot-nginx \
    py3-pip \
    openssl

RUN pip install j2cli

RUN curl -sLo /usr/local/bin/wait-for https://raw.githubusercontent.com/eficode/wait-for/master/wait-for \
    && chmod +x /usr/local/bin/wait-for

COPY image/ /
