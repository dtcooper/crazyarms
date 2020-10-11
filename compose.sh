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

get_bool() {
    # prompt, env name, default (0 = false / 1 = true)
    if [ "$3" = 1 ]; then
        PROMPT='Y/n'
    else
        PROMPT='y/N'
    fi

    while true; do
        read -p "$1 [$PROMPT]? " VALUE
        VALUE="${VALUE:0:1}"
        VALUE="${VALUE^^}"
        if [ "$VALUE" = 'Y' ]; then
            VALUE=1; break
        elif [ "$VALUE" = 'N' ]; then
            VALUE=0; break
        elif [ -z "$VALUE" ]; then
            VALUE="$3"; break
        fi
    done

    .env set "$2=$VALUE"
}

get_str() {
    # prompt, env name, default (optional, otherwise required)
    if [ "$3" ]; then
        PROMPT="$1 [$3]"
    else
        PROMPT="$1 (required)"
    fi

    while true; do
        read -p "${PROMPT}? " VALUE
        if [ "$VALUE" ]; then
            break
        elif [ "$3" ]; then
            VALUE="$3"; break
        fi
    done

    .env set "$2=$VALUE"
}

if [ ! -f .env ]; then
    FIRST_RUN=1
    cp .default.env .env
elif [ "$1" = '--force-first-run' ]; then
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

    get_str 'Domain name' DOMAIN_NAME 'localhost'
    get_bool 'Use HTTPS with letsencrypt (must have a valid domain)' HTTPS_ENABLED 0
    if .env get HTTPS_ENABLED && [ "$REPLY" = 1 ]; then
        get_str 'Administrator email for letsencrypt' HTTPS_CERTBOT_EMAIL
    fi

    get_bool 'Run Icecast service (kh branch)' ICECAST_ENABLED 1
    get_bool 'Enable Zoom (for DJs to broadcast using a Zoom room)' ZOOM_ENABLED 0
    get_bool 'Enable email notifications (via SMTP, like GMail)' EMAIL_ENABLED 0
    if .env get EMAIL_ENABLED && [ "$REPLY" = 1 ]; then
        get_str 'SMTP server, ie smtp.gmail.com' EMAIL_SMTP_SERVER
        get_str 'STMP port' EMAIL_SMTP_PORT 587
        get_str 'STMP username, ie user@gmail.com' EMAIL_SMTP_USERNAME
        get_str 'STMP password (WARNING: stored in plain text)' EMAIL_SMTP_PASSWORD
    fi

    echo
    echo "Setup completed! Settings saved in \`.env' file."
    echo
    echo '########################################'
fi

source .env

COMPOSE_ARGS='--env-file .env --project-directory . -f docker-compose/base.yml'

# Enable compose files for services
for CONF in https icecast zoom email; do
    CONF_VAR="${CONF^^}_ENABLED"
    CONF_VAL="${!CONF_VAR}"
    if [ "$CONF_VAL" -a "$CONF_VAL" != '0' ]; then
        COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose/$CONF.yml"
    fi
done

if [ -f 'docker-compose/overrides.yml' ]; then
    COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose/overrides.yml"
fi

set -x
docker-compose $COMPOSE_ARGS $@
