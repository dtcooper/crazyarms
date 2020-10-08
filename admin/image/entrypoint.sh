#!/bin/bash
. /usr/local/bin/dotenv

if [ -z "$(dotenv -f /.env get SECRET_KEY)" ]; then
    # Set secret key on first run (.env set uses mv, so we need to use a temporary file)
    cp /.env /tmp/.env
    .env -f /tmp/.env set SECRET_KEY="'$(tr -dc 'a-z0-9!@#$%^&*(-_=+)' < /dev/urandom | head -c50)'"
    cp /tmp/.env /.env
    rm /tmp/.env
fi


if [ "$#" = 0 ]; then
    ./manage.py init_services
    DEBUG="$(dotenv -f /.env get DEBUG)"

    if [ "$DEBUG" -a "$DEBUG" != '0' ]; then
        exec ./manage.py runserver
    else
        wait-for-it -t 0 db:5432

        ./manage.py migrate
        ./manage.py collectstatic --noinput

        GUNICORN_WORKERS="$(dotenv -f /.env get GUNICORN_WORKERS)"
        if [ -z "$GUNICORN_WORKERS" ]; then
            GUNICORN_WORKERS="$(python -c 'import multiprocessing as m; print(max(m.cpu_count() // 2, 1))')"
        fi

        GUNICORN_ARGS="-w $GUNICORN_WORKERS"
        if [ "$DEBUG" -a "$DEBUG" != '0' ]; then
            GUNICORN_ARGS="$GUNICORN_ARGS --reload"
        fi

        exec gunicorn $GUNICORN_ARGS -b 0.0.0.0:8000 --access-logfile - wsgi
    fi
else
    exec $@
fi
