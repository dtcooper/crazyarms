#!/bin/sh

if [ -z "$CONTAINER_NAME" ]; then
    echo 'Please run with CONTAINER_NAME set.'
    exit 1
fi

ln -s "/config/${CONTAINER_NAME}/supervisor" /etc/supervisor/conf.d

exec "$@"
