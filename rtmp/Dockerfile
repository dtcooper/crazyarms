FROM nginx:alpine AS builder

# Thanks https://gist.github.com/hermanbanken/96f0ff298c162a522ddbba44cad31081

RUN wget -qO nginx.tar.gz "http://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz"  \
    && wget -qO rtmp.tar.gz "https://github.com/arut/nginx-rtmp-module/archive/master.tar.gz"

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
    && tar -xzvf rtmp.tar.gz \
    && RTMPDIR="$(pwd)/nginx-rtmp-module-master" \
    && cd /usr/src/nginx-$NGINX_VERSION \
    && ./configure --with-compat $CONFARGS --add-dynamic-module=$RTMPDIR \
    && make && make install

FROM nginx:alpine

COPY --from=builder /usr/local/nginx/modules/ngx_rtmp_module.so /usr/local/nginx/modules/ngx_rtmp_module.so

RUN apk add --no-cache ffmpeg

COPY image/ /
