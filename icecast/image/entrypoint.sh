#!/bin/sh

if [ "$#" -gt 0 ]; then
    exec $@
fi

CONF=/etc/icecast.xml

if [ ! -e "/etc/icecast.xml" ]; then
    echo "Waiting for /etc/icecast.xml"
    while [ ! -e "/etc/icecast.xml" ]; do
        sleep 0.5
    done
fi

echo 'Running config change detection daemon'
nohup inotifyd reload_icecast.sh /etc/icecast.xml:c &

echo 'Starting Icecast'
exec icecast -c "$CONF"
