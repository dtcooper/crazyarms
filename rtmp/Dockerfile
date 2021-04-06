FROM nginx:stable-alpine AS builder

# TODO: Pin version of nginx-rtmp

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
    && curl -sL "https://github.com/arut/nginx-rtmp-module/archive/master.tar.gz" | tar xzf -

RUN CONFARGS=$(nginx -V 2>&1 | sed -n -e 's/^.*arguments: //p') \
    CONFARGS=${CONFARGS/-Os -fomit-frame-pointer/-Os} \
    && cd "nginx-${NGINX_VERSION}" \
    && ./configure --with-compat $CONFARGS "--add-dynamic-module=../nginx-rtmp-module-master" \
    && make && make install


FROM nginx:stable-alpine

COPY --from=builder /usr/lib/nginx/modules/ngx_rtmp_module.so /usr/local/nginx/modules/ngx_rtmp_module.so

RUN apk add --no-cache ffmpeg

COPY image/ /
