#!/bin/bash

source /.env

if [ "$#" = 0 ]; then
    wait-for-it -t 0 db:5432
    ./manage.py migrate
    ./manage.py init_services

    if [ "$DEBUG" -a "$DEBUG" != '0' ]; then
        exec ./manage.py runserver
    else
        ./manage.py collectstatic --noinput

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
