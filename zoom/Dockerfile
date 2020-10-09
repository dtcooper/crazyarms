FROM ubuntu:20.04

ENV DISPLAY=:0

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        gnupg \
        icewm \
        supervisor \
        wget \
        x11vnc \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

RUN wget -qO /tmp/zoom.deb https://zoom.us/client/latest/zoom_amd64.deb \
    && wget -qO - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo 'deb http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        /tmp/zoom.deb \
        google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* /tmp/*.deb \
    && adduser --gecos '' --disabled-password user

RUN rmdir /etc/supervisor/conf.d && ln -s /config/zoom/supervisor /etc/supervisor/conf.d \
    && mkdir -p /home/user/.config && chown user:user /home/user/.config

ADD image/ /

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
