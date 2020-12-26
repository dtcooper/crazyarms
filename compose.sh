#!/usr/bin/env bash

if ! command -v docker-compose >/dev/null 2>&1; then
    echo "\`docker-compose' command required. Please install."
    exit 1
fi

cd "$(dirname "$@")"

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
        VALUE="$(echo "$VALUE" | awk '{ print toupper($0) }')"
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

cd "$(dirname "$0")"

FIRST_RUN=
if [ ! -f .env ]; then
    FIRST_RUN=1
    cp .default.env .env
elif [ "$1" = '--first-run' -o "$1" = '--setup' ]; then
    FIRST_RUN=1
    shift 1
fi

if [ "$FIRST_RUN" ]; then
    echo
    echo '########################'
    echo 'Crazy Arms Radio Backend'
    echo '########################'
    echo
    echo 'Welcome to Crazy Arms Radio Backend (CARB). Before we get started, '
    echo "you'll have to answer a few questions to configure its services."
    echo

    get_str 'Domain name' DOMAIN_NAME 'localhost'
    get_str 'Timezone' TIMEZONE 'US/Pacific'

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
        get_str 'STMP password (WARNING: stored in plain text in the .env file)' EMAIL_SMTP_PASSWORD
        get_bool 'Does the SMTP server use TLS?' EMAIL_SMTP_USE_TLS 1
    fi

    echo
    echo "Setup completed! Settings saved in \`.env' file. You can reconfigure"
    echo 'things at any time by editing this file.'
    echo
    if [ "$#" = 0 ]; then
        echo "To start CARB, run \`$0 up'."
        echo
    fi
fi

source .env

if [ "$#" = 0 ]; then
    if [ -z "$FIRST_RUN" ]; then
        echo "Provide a command for docker-compose, i.e. \`$0 up', or \`$0 help' for help."
    fi
    exit 0
fi

if [ -z "$SECRET_KEY" ]; then
    .env set SECRET_KEY="'$(LC_CTYPE=C tr -dc 'a-z0-9!@#%^&*(-_=+)' < /dev/urandom | head -c50)'"
    source .env
fi

COMPOSE_ARGS='--env-file .env --project-directory .'
ALL_SERVICES=
if [ "$1" = '--all-services' -o "$1" = '--all' ]; then
    ALL_SERVICES=1
    shift 1
fi

if [ "$1" = '--test' -o "$1" = test ]; then
    COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose/test.yml"
    if [ "$1" = '--test' ]; then
        shift 1
    else
        shift $#
    fi
    if [ "$#" = 0 ]; then
        set -- "$@" run --rm test
    fi
else
    COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose/base.yml"

    # Enable compose files for services
    for CONF in https icecast zoom harbor-telnet-web rtmp; do
        CONF_VAR="$(echo "$CONF" | LC_CTYPE=C tr '[:lower:]-' '[:upper:]_')_ENABLED"
        CONF_VAL="${!CONF_VAR}"
        if [ "$CONF_VAL" -a "$CONF_VAL" != '0' -o "$ALL_SERVICES" ]; then
            COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose/$CONF.yml"
        fi
    done

    if [ -f 'docker-compose/overrides.yml' ]; then
        COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose/overrides.yml"
    fi
fi

# Make imports/ folder with current user permissions for easy of copying
mkdir -p imports

export CARB_VERSION="$(git describe --tags --always --dirty 2>/dev/null || echo unknown)"
.env -f .version set "CARB_VERSION=$CARB_VERSION"

if [ "$1" = 'version' ]; then
    echo "Crazy Arms Radio Backend version: $CARB_VERSION"
else
    set -x
fi
docker-compose $COMPOSE_ARGS "$@"
