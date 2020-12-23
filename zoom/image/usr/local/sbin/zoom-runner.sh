#!/bin/sh

# Constants
ROOM_INFO_KEY='zoom-runner:room-info'
SLEEP_INTERVAL=2.5
MEETING_USER='Broadcast+Bot'  # TODO: Meeting user could be SHOW ENDS AT
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
            echo "Meeting ID not found at redis key $ROOM_INFO_KEY. Possibly a bad redis key. Not starting."
            sleep "$SLEEP_INTERVAL"
            continue
        fi

        # Start up Zoom service
        if ! zoom_service_running; then
            echo "Starting Zoom and enabling it on the harbor."
            supervisorctl start zoom

            # Wait for Zoom to boot
            while ! xdo search --name "$ROOT_WINDOW_NAME" >/dev/null; do
                sleep 0.05
            done

            sleep 2.5
        fi

        # Enable Zoom source on harbor
        # TODO: is there a better way to do this + save state on harbor restart during a Zoom show?
        #       is this script the best place to execute this? (for one it pollutes harbor logs)
        # Maybe this can happen at:
        #   1. Show start time
        #   2. Show end time
        #   3. When harbor boots it can check if redis key is set
        echo 'var.set zoom_enabled = true\nquit' | nc -w 2 harbor 1234 > /dev/null

        # Open meeting window
        MEETING_WINDOW="$(xdo search --name "$MEETING_WINDOW_NAME")"
        if [ -z "$MEETING_WINDOW" ]; then
            echo "Opening Meeting ID $MEETING_ID by request from user $MEETING_USERNAME (id = $MEETING_USER_ID)."
            # TODO: seems to join multiple times when using a waiting room, need to confirm + fix that
            as_user xdg-open "zoommtg://zoom.us/join?action=join&confno=$MEETING_ID&uname=$MEETING_USER&pwd=$MEETING_PWD"
            sleep 10

            # Make sure meeting window exists
            MEETING_WINDOW="$(xdo search --name "$MEETING_WINDOW_NAME")"
            if [ -z "$MEETING_WINDOW" ]; then
                echo "Error finding window named '$MEETING_WINDOW_NAME'. Meeting window did not open."
                sleep "$SLEEP_INTERVAL"
                continue
            fi
        fi

        # Select Audio pesky conference options popup that occasionally appears
        AUDIO_CONFERENCE_OPTIONS_WINDOW="$(xdo search --onlyvisible --name "$AUDIO_CONFERENCE_OPTIONS_WINDOW_NAME")"
        if [ "$AUDIO_CONFERENCE_OPTIONS_WINDOW" ]; then
            echo 'Found audio conference options. Selecting default.'
            sleep 1
            # Move mouse to the spot correct spot selects computer speakers
            xdo mousemove --window "$AUDIO_CONFERENCE_OPTIONS_WINDOW" \
                "$AUDIO_CONFERENCE_OPTIONS_CLICK_X" \
                "$AUDIO_CONFERENCE_OPTIONS_CLICK_Y"
            sleep 0.25
            # Click it
            xdo click --window "$AUDIO_CONFERENCE_OPTIONS_WINDOW" 1
            sleep 1
        fi

        # Minimize the Window, likely improves performance
        MEETING_WINDOW_VISIBLE="$(xdo search --onlyvisible --name "$MEETING_WINDOW_NAME")"
        if [ "$MEETING_WINDOW_VISIBLE" ]; then
            echo 'Meeting found maximized. Minimizing window.'
            xdo windowminimize "$MEETING_WINDOW_VISIBLE"
            sleep 1
        fi

    else
        echo "No zoom room info found at redis key $ROOM_INFO_KEY. Disabling Zoom broadcasting on harbor."
        echo 'var.set zoom_enabled = false\nquit' | nc -w 2 harbor 1234 > /dev/null

        # If room is running, close it
        MEETING_WINDOW="$(xdo search --name "$MEETING_WINDOW_NAME")"
        if [ "$MEETING_WINDOW" ]; then
            echo 'Closing meeting window.'
            # Focus it
            xdo windowactivate "$MEETING_WINDOW"
            sleep 1
            # Send a close window key combo
            xdo key --window "$MEETING_WINDOW" --clearmodifiers 'alt+F4'
            sleep 1
            # Press enter
            xdo key --window "$MEETING_WINDOW" --clearmodifiers Return
            sleep 1
        fi
    fi

    sleep "$SLEEP_INTERVAL"
done
