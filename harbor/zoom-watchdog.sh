#!/bin/sh

if [ -z "$1" -o -z "$2" ]; then
    echo "Usage $(basename "$0") <id> <password>"
    exit 0
fi

if [ -z "$DISPLAY" ]; then
    echo 'No DISPLAY found. Exiting.'
    exit 1
fi

MEETING_ID=$1
MEETING_PWD=$2
MEETING_USER="SHARE+YOUR+COMPUTER%27S+SOUND"

ZOOM_LEAVE_NAME="Leave Meeting"
ZOOM_LEAVE_OK_BTN_POS_X=504
ZOOM_LEAVE_OK_BTN_POS_Y=152

ZOOM_WINDOW_NAME="Zoom Meeting"

ZOOM_FLOAT_NAME="zoom_linux_float_video_window"
ZOOM_FLOAT_WINDOW_MIN_BTN_POS_X=20
ZOOM_FLOAT_WINDOW_MIN_BTN_POS_Y=90
ZOOM_FLOAT_WINDOW_MIN_HEIGHT=85

while true; do
    if ! pgrep -fu $(whoami) /opt/zoom/zoom > /dev/null; then
        echo "$(date) - Zoom not running."
        if [ -f /.dockerenv ]; then
            break
        else
            continue
        fi
    fi

    # Close a previous timeout
    LEAVE_WINDOW="$(xdotool search --onlyvisible --name "$ZOOM_LEAVE_NAME")"
    if [ "$LEAVE_WINDOW" ]; then
        echo "$(date) - Timeout window found. Closing it."
        xdotool mousemove --window "$LEAVE_WINDOW" \
            "$ZOOM_LEAVE_OK_BTN_POS_X" \
            "$ZOOM_LEAVE_OK_BTN_POS_Y"
        sleep 1
        xdotool click --window "$LEAVE_WINDOW" 1
        sleep 1
    fi

    # Find zoom meeting window
    MAIN_WINDOW="$(xdotool search --name "$ZOOM_WINDOW_NAME")"
    if [ -z "$MAIN_WINDOW" ]; then
        echo "$(date) - Meeting not running. Opening meeting ID $MEETING_ID."
        xdg-open "zoommtg://zoom.us/join?action=join&confno=$MEETING_ID&uname=$MEETING_USER&pwd=$MEETING_PWD"
        sleep 5
        MAIN_WINDOW="$(xdotool search --name "$ZOOM_WINDOW_NAME")"
    fi
    if [ -z "$MAIN_WINDOW" ]; then
        echo "$(date) - Error finding window named '$ZOOM_WINDOW_NAME'."
        if [ -f /.dockerenv ]; then
            break
        else
            continue
        fi
    fi

    # If it's maximized, minimize it
    if xwininfo -id "$MAIN_WINDOW" | grep 'Map State:' | grep -q IsViewable; then
        echo "$(date) - Window '$ZOOM_WINDOW_NAME' found maximized. Minimizing."
        xdotool windowminimize "$MAIN_WINDOW"
        sleep 3
    fi

    FLOAT_WINDOW="$(xdotool search --name "$ZOOM_FLOAT_NAME")"
    if [ -z "$FLOAT_WINDOW" ]; then
        echo "$(date) - Error finding window named '$ZOOM_FLOAT_NAME'."
        if [ -f /.dockerenv ]; then
            break
        else
            continue
        fi
    fi

    if [ "$(xwininfo -id "$FLOAT_WINDOW" | grep 'Height:' | awk '{print $2}')" \
            -gt "$ZOOM_FLOAT_WINDOW_MIN_HEIGHT" ]; then
        echo "$(date) - Float window found maximized. Minimizing."
        xdotool mousemove --window "$FLOAT_WINDOW" \
            "$ZOOM_FLOAT_WINDOW_MIN_BTN_POS_X" \
            "$ZOOM_FLOAT_WINDOW_MIN_BTN_POS_Y"

        sleep 1
        xdotool click --window "$FLOAT_WINDOW" 1
    fi

    if [ -f /.dockerenv ]; then
        break
    fi

    sleep 10
done
