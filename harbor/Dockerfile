FROM ubuntu:20.04

ENV DISPLAY=:0
ENV CHROMIUM_USER_FLAGS="--no-first-run --no-sandbox"

RUN apt-get update \
    && apt-get -y upgrade \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        gnupg \
        icecast2 \
        icewm \
        libsox-fmt-all \
        liquidsoap \
        nginx \
        novnc \
        pulseaudio \
        sox \
        sudo \
        supervisor \
        websockify \
        wget \
        x11vnc \
        xvfb \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo 'deb http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && wget -P /tmp https://zoom.us/client/latest/zoom_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/zoom_amd64.deb \
    && ln -fs /usr/share/zoneinfo/America/Los_Angeles /etc/localtime \
    && dpkg-reconfigure --frontend noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/*/tmp/zoom_amd64.deb

# Prevasives fix for liquidsoap 1.4.1 on Debian/Ubuntu
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=956564#5
RUN mkdir /usr/share/liquidsoap/1.4.1 \
    && ln -s /usr/share/liquidsoap/libs /usr/share/liquidsoap/1.4.1/

RUN adduser --gecos '' --disabled-password user \
    && adduser user sudo \
    && sed -i 's/^\(%sudo.\+\)ALL$/\1NOPASSWD:ALL/' /etc/sudoers

USER user
ENTRYPOINT ["/entrypoint.sh"]
ADD image /
