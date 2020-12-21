#!/bin/bash

. /.env

on_die ()
{
    # per nginx-rtmp manual, re: killing ffmpeg
    pkill -KILL -P $$
}

EXTRA_FFMPEG_ARGS=

if [ "$DEBUG" -a "$DEBUG" != '0' ]; then
    mkdir -p /tmp/ffmpeg-report
    cd /tmp/ffmpeg-report
    EXTRA_FFMPEG_ARGS='-report'
else
    EXTRA_FFMPEG_ARGS='-hide_banner -loglevel warning'
fi

trap 'on_die' TERM
# Just use a wav container (that'll strip out video)
ffmpeg $EXTRA_FFMPEG_ARGS -re -i "rtmp://localhost:1935/stream/$1" -f wav \
    -content_type 'audio/wav' "icecast://!:$1@harbor:8001/stream" &
wait

# Disconnect when ffmpeg quits unexpectedly, ie harbor restart, boot, etc
curl "http://127.0.0.1:8080/control/drop/publisher?app=stream&name=$1"
