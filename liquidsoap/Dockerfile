FROM ubuntu:20.04

ENV LIQUIDSOAP_VERSION "1.4.4"

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        festival \
        festvox-kallpc16k \
        ffmpeg \
        jq \
        libsox-fmt-all \
        pulseaudio \
        redis-tools \
        sox \
        supervisor \
        wget \
    && rm -rf /var/lib/apt/lists/*

RUN ARCH="$(dpkg --print-architecture)" \
    && wget -qO /tmp/liquidsoap.deb "https://github.com/savonet/liquidsoap/releases/download/v${LIQUIDSOAP_VERSION}/liquidsoap-v${LIQUIDSOAP_VERSION}_${LIQUIDSOAP_VERSION}-ubuntu-focal-${ARCH}-1_${ARCH}.deb" \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        /tmp/liquidsoap.deb \
    && rm -rf /var/lib/apt/lists/* /tmp/*.deb

RUN wget -qO /usr/local/bin/wait-for-it https://raw.githubusercontent.com/vishnubob/wait-for-it/81b1373f/wait-for-it.sh \
    && chmod +x /usr/local/bin/wait-for-it

RUN rmdir /etc/supervisor/conf.d

COPY image/ /

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
