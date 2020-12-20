#!/bin/sh

. /.env

URL='http://app:8000/api/sftp-upload/'
JSON_IN="$(jq -nc --arg p "$3" '{"path": $p}')"

curl -d "$JSON_IN" -H "X-Carb-Secret-Key: $SECRET_KEY" "$URL"
