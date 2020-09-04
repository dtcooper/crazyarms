FROM ubuntu:20.04

ENV DISPLAY=:0

RUN apt-get update \
    && apt-get -y upgrade \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        festival \
        festvox-kallpc16k \
        ffmpeg \
        git \
        gnupg \
        icecast2 \
        icewm \
        libsox-fmt-all \
        nginx \
        novnc \
        pulseaudio \
        python3-pip \
        rlwrap \
        sox \
        sudo \
        supervisor \
        telnet \
        websockify \
        wget \
        x11-utils \
        x11vnc \
        xdotool \
        xvfb \
    && wget -qP /tmp https://zoom.us/client/latest/zoom_amd64.deb \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo 'deb http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list \
    && apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 20D63CCDDD0F62C2 \
    && echo deb http://deb.liquidsoap.info/ubuntu focal main > /etc/apt/sources.list.d/liquidsoap.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        /tmp/zoom_amd64.deb \
        google-chrome-stable \
        liquidsoap-1.4.2 \
    && ln -fs /usr/share/zoneinfo/America/Los_Angeles /etc/localtime \
    && dpkg-reconfigure --frontend noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/* /tmp/zoom_amd64.deb

ADD requirements.txt /tmp
RUN pip3 install youtube-dl -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN adduser --gecos '' --disabled-password user \
    && adduser user sudo \
    && sed -i 's/^\(%sudo.\+\)ALL$/\1NOPASSWD:ALL/' /etc/sudoers \
    && addgroup --system reboot \
    && echo '%reboot ALL=NOPASSWD:/sbin/reboot' > /etc/sudoers.d/reboot

USER user
WORKDIR /mnt/harbor
ENTRYPOINT ["/entrypoint.sh"]
ADD image /
