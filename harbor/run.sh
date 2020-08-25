#!/bin/bash

cd "$(dirname "$0")"

dotenv () {
  set -a
  source "$1"
  set +a
}

if [ "$(uname -s)" = 'Darwin' ]; then
    USE_DOCKER=1
fi

if [ "$USE_DOCKER" -a ! -f /.dockerenv ]; then
    CONTAINER=bmir-harbor
    PORTS="80 1234 1235 2097 5900 8000 8001"

    if echo "$@" | fgrep -q -- '--build' && shift \
            || [ -z "$(docker images -q "$CONTAINER" 2> /dev/null)" ]; then
        docker build -t "$CONTAINER" .
    fi

    # --cap-add=SYS_ADMIN for Chrome
    PORTS="80 1234 1235 2097 5900 8000 8001"
    exec docker run --cap-add=SYS_ADMIN --init --rm -it -v "$PWD:/mnt" \
        $(for p in $PORTS; do echo "-p $p:$p "; done) "$CONTAINER" $@
else
    dotenv env.vars.default

    # Global variables
    if [ -f env.vars ]; then
        dotenv env.vars
    fi

    # Overrides
    if [ -f "$ENVFILE" ]; then
        dotenv "$ENVFILE"
    fi

    if [ -f "$1" ]; then
        SCRIPT="$1"
        shift 1
    else
        SCRIPT=harbor.liq
    fi

    exec liquidsoap "$SCRIPT" -- $@
fi
