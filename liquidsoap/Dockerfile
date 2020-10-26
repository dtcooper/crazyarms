FROM ubuntu:20.04

ENV LIQUIDSOAP_VERSION "1.4.3"

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        festival \
        festvox-kallpc16k \
        ffmpeg \
        libsox-fmt-all \
        pulseaudio \
        python3 \
        python3-pip \
        sox \
        supervisor \
        wget \
    && rm -rf /var/lib/apt/lists/*

RUN wget -qO /tmp/liquidsoap.deb "https://github.com/savonet/liquidsoap/releases/download/v${LIQUIDSOAP_VERSION}/liquidsoap-v${LIQUIDSOAP_VERSION}_${LIQUIDSOAP_VERSION}-ubuntu-focal-amd64-1_amd64.deb" \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        /tmp/liquidsoap.deb \
    && rm -rf /var/lib/apt/lists/* /tmp/*.deb

RUN pip3 install --no-cache-dir youtube-dl

RUN rmdir /etc/supervisor/conf.d

COPY image/ /

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
