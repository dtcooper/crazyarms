#!/bin/sh

PID="$(pgrep '^icecast$')"

if [ "$PID" ]; then
    kill -SIGHUP "$PID"
fi
