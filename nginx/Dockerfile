FROM nginx:alpine AS builder

# TODO: Pin version of nchan

# Adapted from https://gist.github.com/hermanbanken/96f0ff298c162a522ddbba44cad31081#gistcomment-3555604
RUN apk add --no-cache \
        curl \
        gcc \
        gd-dev \
        geoip-dev \
        gnupg \
        libc-dev \
        libxslt-dev \
        linux-headers \
        make \
        openssl-dev \
        pcre-dev \
        zlib-dev

WORKDIR /tmp

RUN curl -sL "http://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz" | tar xzf - \
    && curl -sL "https://github.com/slact/nchan/archive/master.tar.gz" | tar xzf -

RUN CONFARGS=$(nginx -V 2>&1 | sed -n -e 's/^.*arguments: //p') \
    CONFARGS=${CONFARGS/-Os -fomit-frame-pointer -g/-Os} \
    && cd "nginx-${NGINX_VERSION}" \
    && ./configure --with-compat $CONFARGS "--add-dynamic-module=../nchan-master" \
    && make && make install


FROM nginx:alpine

COPY --from=builder /usr/lib/nginx/modules/ngx_nchan_module.so /usr/local/nginx/modules/ngx_nchan_module.so

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

RUN sed -i '1s/^/# Load nchan module\nload_module \/usr\/local\/nginx\/modules\/ngx_nchan_module.so;\n/' /etc/nginx/nginx.conf

COPY image/ /
