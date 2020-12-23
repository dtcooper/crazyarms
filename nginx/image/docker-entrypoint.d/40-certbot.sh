#!/bin/sh

ME=$(basename $0)

. /.env

if [ "$HTTPS_ENABLED" -a "$HTTPS_ENABLED" != '0' ]; then
    CERT_PATH="/etc/letsencrypt/live/${DOMAIN_NAME}"

    if [ ! -f "$CERT_PATH/fullchain.pem" -o ! -f "$CERT_PATH/privkey.pem" ]; then
        echo >&3 "$ME: certbot hasn't created a certificate yet, so generating a self-signed one"
        mkdir -p "$CERT_PATH"
        openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
            -keyout "$CERT_PATH/privkey.pem" \
            -out "$CERT_PATH/fullchain.pem" \
            -subj "/C=US/O=CARB Self-Signed/CN=$DOMAIN_NAME"
    fi

    CERTBOT_LOG=/var/log/certbot_daemon.log
    echo >&3 "$ME: running certbot daemon (https), log in $CERTBOT_LOG"
    nohup certbot-daemon.sh >"$CERTBOT_LOG" 2>&1 &
else
    echo >&3 "$ME: https disabled by configuration"
fi
