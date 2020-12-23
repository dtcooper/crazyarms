FROM nginx:alpine AS builder

# Thanks https://gist.github.com/hermanbanken/96f0ff298c162a522ddbba44cad31081
ENV NCHAN_VERSION 1.2.7

RUN wget -O nginx.tar.gz "http://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz"  \
    && wget -O nchan.tar.gz "https://github.com/slact/nchan/archive/v${NCHAN_VERSION}.tar.gz"

RUN apk add --no-cache --virtual .build-deps \
  gcc \
  libc-dev \
  make \
  openssl-dev \
  pcre-dev \
  zlib-dev \
  linux-headers \
  curl \
  gnupg \
  libxslt-dev \
  gd-dev \
  geoip-dev

RUN CONFARGS=$(nginx -V 2>&1 | sed -n -e 's/^.*arguments: //p') \
    mkdir /usr/src \
    && tar -zxC /usr/src -f nginx.tar.gz \
    && tar -xzvf nchan.tar.gz \
    && NCHANDIR="$(pwd)/nchan-${NCHAN_VERSION}" \
    && cd /usr/src/nginx-$NGINX_VERSION \
    && ./configure --with-compat $CONFARGS --add-dynamic-module=$NCHANDIR \
    && make && make install

FROM nginx:alpine

COPY --from=builder /usr/local/nginx/modules/ngx_nchan_module.so /usr/local/nginx/modules/ngx_nchan_module.so

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
