#!/bin/bash
. /usr/local/bin/dotenv
.env -f /.env export

check_self_signed() {
    openssl x509 -noout -subject -nameopt multiline -in "$CERT_PATH/fullchain.pem" \
        | grep -q 'organizationName *= *CARB Self-Signed'
}

log() {
    echo "$(date) - $1"
}

run_certbot() {
    certbot_args=
    if [ "$HTTPS_CERTBOT_STAGING" -a "$HTTPS_CERTBOT_STAGING" != '0' ]; then
        log 'Using staging certificate (for testing)'
        certbot_args='--server https://acme-staging-v02.api.letsencrypt.org/directory'
    fi

    if [ "$HTTPS_CERTBOT_FORCE_RENEW" -a "$HTTPS_CERTBOT_FORCE_RENEW" != '0' ]; then
        # undocumented, for testing
        log "Forcing certificate renwal"
        certbot_args="$certbot_args --force-renewal"
    fi

    certbot certonly --agree-tos --keep -n --text --email "$HTTPS_CERTBOT_EMAIL" \
        -d "$DOMAIN_NAME" --http-01-port 8080 --standalone --preferred-challenges http-01 \
        --deploy-hook 'nginx -s reload' $certbot_args
}

wait-for-it -t 0 localhost:80

CERT_PATH="/etc/letsencrypt/live/${DOMAIN_NAME}"
if check_self_signed; then
    log 'Found self-signed certificate, removing'
    rm -r "$CERT_PATH"
fi

while true; do
    log 'Running cerbot'
    run_certbot
    log 'Sleeping for 7 days'
    sleep 604800  # 7 days
done
