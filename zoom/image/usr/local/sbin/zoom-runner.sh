#!/bin/sh

# Constants
ROOM_INFO_KEY='zoom-runner:room-info'
SLEEP_INTERVAL=3
MEETING_USER='Broadcast+Bot'
ROOT_WINDOW_NAME='Zoom Cloud Meetings'
AUDIO_CONFERENCE_OPTIONS_WINDOW_NAME='audio conference options'
AUDIO_CONFERENCE_OPTIONS_CLICK_X=290
AUDIO_CONFERENCE_OPTIONS_CLICK_Y=154
MEETING_WINDOW_NAME='Zoom Meeting'

# Variables
ZOOM_INFO=
MEETING_ID=
MEETING_PWD=
MEETING_USERNAME=
MEETING_USER_ID=

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
    ROOM_INFO="$(redis-cli -h redis get $ROOM_INFO_KEY)"

    if [ "$ROOM_INFO" ]; then
        eval "$ROOM_INFO"
        if [ -z "$MEETING_ID" ]; then
            echo "Meeting ID not found at redis key $ROOM_INFO_KEY. Not starting."
            sleep "$SLEEP_INTERVAL"
            continue
        fi

        if ! zoom_service_running; then
            echo "Starting Zoom."
            supervisorctl start zoom

            # Wait for Zoom to boot
            while ! xdo search --name "$ROOT_WINDOW_NAME" >/dev/null; do
                sleep 0.05
            done

            sleep 2.5
        fi

        MEETING_WINDOW="$(xdo search --name "$MEETING_WINDOW_NAME")"
        if [ -z "$MEETING_WINDOW" ]; then
            echo "Opening Meeting ID $MEETING_ID by request from user $MEETING_USERNAME (id = $MEETING_USER_ID)."
            # TODO: seems to join multiple times when using a waiting room, need to confirm + fix that
            as_user xdg-open "zoommtg://zoom.us/join?action=join&confno=$MEETING_ID&uname=$MEETING_USER&pwd=$MEETING_PWD"
            sleep 10
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

    else
        echo "No zoom room info found at redis key $ROOM_INFO_KEY."
        MEETING_WINDOW="$(xdo search --name "$MEETING_WINDOW_NAME")"
        if [ "$MEETING_WINDOW" ]; then
            echo 'Closing meeting window.'
            xdo windowactivate "$MEETING_WINDOW"
            sleep 1
            xdo key --window "$MEETING_WINDOW" --clearmodifiers 'alt+F4'
            sleep 1
            xdo key --window "$MEETING_WINDOW" --clearmodifiers Return
            sleep 1
        fi
    fi

    sleep "$SLEEP_INTERVAL"
done
