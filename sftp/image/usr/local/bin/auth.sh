#!/bin/sh

. /.env

URL='http://app:8000/api/sftp-auth/'
JSON_IN="$(jq -nc --arg u "$SFTPGO_AUTHD_USERNAME" --arg p "$SFTPGO_AUTHD_PASSWORD" --arg k "$SFTPGO_AUTHD_PUBLIC_KEY" '{"username": $u, "password": $p, "key": $k}')"
JSON_OUT="$(curl -d "$JSON_IN" -H "X-Crazyarms-Secret-Key: $SECRET_KEY" "$URL")"
STATUS="$(echo "$JSON_OUT" | jq -r .status)"

if [ "$STATUS" = 1 ]; then
    HOME_DIR="/sftp_root/$(echo "$JSON_OUT" | jq -r .username)"

    # Create user's home directories with subdirectories based on permissions
    mkdir -p "$HOME_DIR"
    cp /etc/sftp_home_readme.txt "$HOME_DIR/README.txt"

    # These should match api/tasks.py:SFTP_PATH_ASSET_CLASSES
    for PERM_DIR in '/audio-assets/' '/scheduled-broadcast-assets/' '/rotator-assets/'; do
        if [ "$(echo "$JSON_OUT" | jq -r --arg p "$PERM_DIR" '(.permissions | keys)[] | select(. == $p)')" ]; then
            mkdir -p "${HOME_DIR}${PERM_DIR}"
        else
            rm -rf "${HOME_DIR}${PERM_DIR}"
        fi
    done

    echo "$JSON_OUT"
    exit 0
else
    echo '{"status": 0}'
    exit 1
fi
