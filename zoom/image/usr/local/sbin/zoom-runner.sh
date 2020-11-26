#!/bin/sh

# Constants
ROOM_INFO_KEY='zoom-runner:room-info'
SLEEP_INTERVAL=2.5
ZOOM_ROOM_OPEN_WAIT=5
MEETING_USER='SHARE+YOUR+SOUND'
ROOT_WINDOW_NAME='Zoom Cloud Meetings'
AUDIO_CONFERENCE_OPTIONS_WINDOW_NAME='audio conference options'
AUDIO_CONFERENCE_OPTIONS_CLICK_X=290
AUDIO_CONFERENCE_OPTIONS_CLICK_Y=154
MEETING_WINDOW_NAME='Zoom Meeting'

# Variables
ZOOM_INFO=
MEETING_ID=
MEETING_PWD=

zoom_service_running() {
    supervisorctl status zoom | grep -q 'STARTING\|RUNNING\|BACKOFF'
}

as_user() {
    sudo -u user PULSE_SERVER=harbor DISPLAY=:0 "$@"
}

xdo() {
    as_user xdotool "$@"
}

echo "Waiting on redis key $ROOM_INFO_KEY"

while true; do
    PREV_ZOOM_INFO="$ZOOM_INFO"
    ROOM_INFO="$(redis-cli -h redis get $ROOM_INFO_KEY)"

    if [ "$ROOM_INFO" ]; then
        eval "$ROOM_INFO"
        if [ -z "$MEETING_ID" ]; then
            echo "Meeting ID not found at redis key $ROOM_INFO_KEY. Not starting."
            sleep "$SLEEP_INTERVAL"
            continue
        fi

        if ! zoom_service_running; then
            echo 'Starting Zoom.'
            supervisorctl start zoom

            # Wait for Zoom to boot
            while ! xdo search --name "$ROOT_WINDOW_NAME" >/dev/null; do
                sleep 0.05
            done

            sleep 2.5
        fi

        MEETING_WINDOW="$(xdo search --name "$MEETING_WINDOW_NAME")"
        if [ -z "$MEETING_WINDOW" ]; then
            echo "Meeting not running. Opening Meet ID $MEETING_ID."
            as_user xdg-open "zoommtg://zoom.us/join?action=join&confno=$MEETING_ID&uname=$MEETING_USER&pwd=$MEETING_PWD"
            sleep 5
            MEETING_WINDOW="$(xdo search --name "$MEETING_WINDOW_NAME")"
        fi

        if [ -z "$MEETING_WINDOW" ]; then
            echo "Error finding window named '$MEETING_WINDOW_NAME'."
            sleep "$SLEEP_INTERVAL"
            continue
        fi

        AUDIO_CONFERENCE_OPTIONS_WINDOW="$(xdo search --onlyvisible --name "$AUDIO_CONFERENCE_OPTIONS_WINDOW_NAME")"
        if [ "$AUDIO_CONFERENCE_OPTIONS_WINDOW" ]; then
            echo 'Found audio conference options. Selecting default.'
            sleep 1
            xdo mousemove --window "$AUDIO_CONFERENCE_OPTIONS_WINDOW" \
                "$AUDIO_CONFERENCE_OPTIONS_CLICK_X" \
                "$AUDIO_CONFERENCE_OPTIONS_CLICK_Y"
            sleep 0.25
            xdo click --window "$AUDIO_CONFERENCE_OPTIONS_WINDOW" 1
            sleep 1
        fi

        MEETING_WINDOW_VISIBLE="$(xdo search --onlyvisible --name "$MEETING_WINDOW_NAME")"
        if [ "$MEETING_WINDOW_VISIBLE" ]; then
            echo 'Meeting found maximized. Minimizing window.'
            xdo windowminimize "$MEETING_WINDOW_VISIBLE"
            sleep 1
        fi

    elif [ "$PREV_ZOOM_INFO" ]; then
        # Was previously found running
        echo "No zoom room info found at redis key $ROOM_INFO_KEY. Sleeping."
        if zoom_service_running; then
            echo 'Zoom room found running. Stopping.'
            supervisorctl stop zoom
        fi
    fi

    sleep "$SLEEP_INTERVAL"
done
