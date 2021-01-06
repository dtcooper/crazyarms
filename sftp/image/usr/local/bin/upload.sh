#!/bin/sh

. /.env

INFILE=

if [ "$1" = 'upload' ]; then
    # Only run if file *doesn't* end in .filepart (ie, WinSCP pre-rename)
    if ! expr "$3" : '.*\.filepart$' > /dev/null; then
        INFILE="$3"
    fi
elif [ "$1" = 'rename' ]; then
    INFILE="$4"
fi

if [ "$INFILE" ]; then
    URL='http://app:8000/api/sftp-upload/'
    JSON_IN="$(jq -nc --arg p "$INFILE" '{"path": $p}')"
    curl -d "$JSON_IN" -H "X-Crazyarms-Secret-Key: $SECRET_KEY" "$URL"
fi
