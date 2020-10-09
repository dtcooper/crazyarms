#!/usr/bin/env bash

if ! command -v docker-compose >/dev/null 2>&1; then
    echo "\`docker-compose' command required. Please install."
    exit 1
fi

### Copied from https://github.com/bashup/dotenv

__dotenv=
__dotenv_file=
__dotenv_cmd=.env

.env() {
    REPLY=()
    [[ $__dotenv_file || ${1-} == -* ]] || .env.--file .env || return
    if declare -F -- ".env.${1-}" >/dev/null; then .env."$@"; return ; fi
    .env --help >&2; return 64
}

.env.-f() { .env.--file "$@"; }

.env.get() {
    .env::arg "get requires a key" "$@" &&
    [[ "$__dotenv" =~ ^(.*(^|$'\n'))([ ]*)"$1="(.*)$ ]] &&
    REPLY=${BASH_REMATCH[4]%%$'\n'*} && REPLY=${REPLY%"${REPLY##*[![:space:]]}"}
}

.env.parse() {
    local line key
    while IFS= read -r line; do
        line=${line#"${line%%[![:space:]]*}"}  # trim leading whitespace
        line=${line%"${line##*[![:space:]]}"}  # trim trailing whitespace
        if [[ ! "$line" || "$line" == '#'* ]]; then continue ; fi
        if (($#)); then
            for key; do
                if [[ $key == "${line%%=*}" ]]; then REPLY+=("$line"); break;
                fi
            done
        else
            REPLY+=("$line")
        fi
    done <<<"$__dotenv"
    ((${#REPLY[@]}))
}

.env.export() { ! .env.parse "$@" || export "${REPLY[@]}"; }

.env.set() {
    .env::file load || return ; local key saved=$__dotenv
    while (($#)); do
        key=${1#+}; key=${key%%=*}
        if .env.get "$key"; then
            REPLY=()
            if [[ $1 == +* ]]; then shift; continue  # skip if already found
            elif [[ $1 == *=* ]]; then
                __dotenv=${BASH_REMATCH[1]}${BASH_REMATCH[3]}$1$'\n'${BASH_REMATCH[4]#*$'\n'}
            else
                __dotenv=${BASH_REMATCH[1]}${BASH_REMATCH[4]#*$'\n'}
                continue   # delete all occurrences
            fi
        elif [[ $1 == *=* ]]; then
            __dotenv+="${1#+}"$'\n'
        fi
        shift
    done
    [[ $__dotenv == "$saved" ]] || .env::file save
}

.env.puts() { echo "${1-}">>"$__dotenv_file" && __dotenv+="$1"$'\n'; }

.env.generate() {
    .env::arg "key required for generate" "$@" || return
    .env.get "$1" && return || REPLY=$("${@:2}") || return
    .env::one "generate: ouptut of '${*:2}' has more than one line" "$REPLY" || return
    .env.puts "$1=$REPLY"
}

.env.--file() {
    .env::arg "filename required for --file" "$@" || return
    __dotenv_file=$1; .env::file load || return
    (($#<2)) || .env "${@:2}"
}

.env::arg() { [[ "${2-}" ]] || { echo "$__dotenv_cmd: $1" >&2; return 64; }; }

.env::one() { [[ "$2" != *$'\n'* ]] || .env::arg "$1"; }

.env::file() {
    local REPLY=$__dotenv_file
    case "$1" in
    load)
        __dotenv=; ! [[ -f "$REPLY" ]] || __dotenv="$(<"$REPLY")"$'\n' || return ;;
    save)
        if [[ -L "$REPLY" ]] && declare -F -- realpath.resolved >/dev/null; then
            realpath.resolved "$REPLY"
        fi
        { [[ ! -f "$REPLY" ]] || cp -p "$REPLY" "$REPLY.bak"; } &&
        printf %s "$__dotenv" >"$REPLY.bak" && mv "$REPLY.bak" "$REPLY"
    esac
}

### End dotenv

cd "$(dirname "$0")"

FIRST_RUN=

bool() {
    # Second argument is default return value, ie 0 = yes, 1 = no
    if [ -z "$1" ]; then
        return "${2:-0}"
    fi

    [ "${1:0:1}" = 'y' -o "${1:0:1}" = 'Y' ]
}

if [ ! -f .env ]; then
    FIRST_RUN=1
    cp .default.env .env
elif [ "$1" = '--first-run' ]; then
    FIRST_RUN=1
    shift 1
fi

if [ "$FIRST_RUN" ]; then
    echo
    echo '########################################'
    echo
    echo 'Welcome to Crazy Arms Radio Backend!'
    echo
    echo '########################################'
    echo
    echo "Before we get started, you'll have to answer a few questions in order"
    echo 'to decide which services to run. You can change your answers by'
    echo "editing the file \`.env' in this directory."
    echo
    .env set SECRET_KEY="'$(LC_CTYPE=C tr -dc 'a-z0-9!@#$%^&*(-_=+)' < /dev/urandom | head -c50)'"

    read -p 'Domain name [localhost]? ' DOMAIN_NAME
    .env set DOMAIN_NAME="${DOMAIN_NAME:-localhost}"

    read -p 'Use HTTPS with letsencrypt (must have a valid domain) [y/N]? ' HTTPS_ENABLED
    if bool "$HTTPS_ENABLED" 1; then
        .env set HTTPS_ENABLED=1

        while true; do
            read -p 'Administrator email for letsencrypt (required)? ' HTTPS_CERTBOT_EMAIL
            # https://gist.github.com/guessi/82a73ee7eb2b1216eb9db17bb8d65dd1
            EMAIL_REGEX="^([A-Za-z]+[A-Za-z0-9]*((\.|\-|\_)?[A-Za-z]+[A-Za-z0-9]*){1,})@(([A-Za-z]+[A-Za-z0-9]*)+((\.|\-|\_)?([A-Za-z]+[A-Za-z0-9]*)+){1,})+\.([A-Za-z]{2,})+"
            if [[ "$HTTPS_CERTBOT_EMAIL" =~ $EMAIL_REGEX ]]; then
                break
            else
                echo 'Invalid email. Please try again.'
            fi
        done
        .env set HTTPS_CERTBOT_EMAIL="${HTTPS_CERTBOT_EMAIL}"
    else
        .env set HTTPS_ENABLED=0
    fi

    read -p 'Run Icecast service (kh branch) [Y/n]? ' ICECAST_ENABLED
    .env set ICECAST_ENABLED="$(bool "$ICECAST_ENABLED" && echo '1' || echo '0')"

    read -p 'Run Zoom service (for DJs to broadcast using Zoom) [y/N]? ' ZOOM_ENABLED
    .env set ZOOM_ENABLED="$(bool "$ZOOM_ENABLED" 1 && echo '1' || echo '0')"

    echo
    echo "Setup completed! Settings saved in \`.env' file."
    echo
    echo '########################################'
fi

source .env

COMPOSE_ARGS='-f docker-compose.yml'

if [ "$ICECAST_ENABLED" -a "$ICECAST_ENABLED" != '0' ]; then
    COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose.icecast.yml"
fi

if [ "$ZOOM_ENABLED" -a "$ZOOM_ENABLED" != '0' ]; then
    COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose.zoom.yml"
fi

if [ -f 'docker-compose.overrides.yml' ]; then
    COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose.overrides.yml"
fi

docker-compose $COMPOSE_ARGS $@
