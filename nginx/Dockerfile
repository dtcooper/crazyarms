FROM library/nginx:alpine

ENV NOVNC_VERSION "1.2.0"

RUN apk add --no-cache \
        certbot \
        certbot-nginx \
        openssl \
        py3-pip

RUN pip install --no-cache-dir j2cli

RUN curl -sLo /usr/local/bin/wait-for https://raw.githubusercontent.com/eficode/wait-for/master/wait-for \
    curl -sL curl "https://github.com/novnc/noVNC/archive/v${NOVNC_VERSION}.tar.gz" | tar xz -C /tmp \
    && mv "/tmp/noVNC-${NOVNC_VERSION}" /usr/share/noVNC \
    && chmod +x /usr/local/bin/wait-for

COPY image/ /
