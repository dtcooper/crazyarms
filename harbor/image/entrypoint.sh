#!/bin/sh

pulseaudio -n --exit-idle-time=-1 --load=module-native-protocol-unix --load=module-always-sink --start
sudo -E supervisord -c /etc/supervisor/supervisord.conf

if [ "$#" -gt 0 ]; then
    exec $@
else
    exec ./run.sh
fi
