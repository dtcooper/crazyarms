FROM alpine

ENV ICECAST_KH_VERSION "2.4.0-kh15"

RUN apk add --no-cache \
        build-base \
        curl \
        libogg-dev \
        libtheora-dev \
        libvorbis-dev \
        libxslt-dev \
        speex-dev

RUN cd /tmp \
    && curl -sL "https://github.com/karlheyes/icecast-kh/archive/icecast-$ICECAST_KH_VERSION.tar.gz" | tar xzf - \
    && cd "icecast-kh-icecast-$ICECAST_KH_VERSION" \
    && ./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var \
    && make && make install \
    && cd .. && rm -r "icecast-kh-icecast-$ICECAST_KH_VERSION" \
    && addgroup -S icecast && adduser -HSG icecast icecast

RUN rm /etc/icecast.xml && ln -s /config/icecast/icecast.xml /etc/icecast.xml

COPY image/ /

USER icecast
ENTRYPOINT ["/entrypoint.sh"]
CMD []
