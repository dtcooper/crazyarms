#!/bin/bash

if [ "$RUN_HUEY" ]; then
    __RUN_HUEY=1
fi

source /.env

if [ "$#" = 0 ]; then
    # Number of CPUs + 1, since most of our work will be DB + io bound
    RECOMMENDED_NUM_WORKERS="$(python -c 'import multiprocessing as m; print(max(m.cpu_count() // 2 + 1, 2))')"

    if [ "${__RUN_HUEY}" ]; then
        if [ -z "$HUEY_WORKERS" ]; then
            HUEY_WORKERS="$RECOMMENDED_NUM_WORKERS"
        fi
        CMD="./manage.py run_huey --workers $HUEY_WORKERS --worker-type process --simple"
        if [ "$DEBUG" -a "$DEBUG" != '0' ]; then
            watchmedo auto-restart --directory=./ --pattern=*.py --recursive -- $CMD
        else
            $CMD
        fi
    else
        wait-for-it -t 0 db:5432
        ./manage.py migrate
        ./manage.py init_services

        if [ "$DEBUG" -a "$DEBUG" != '0' ]; then
            exec ./manage.py runserver
        else
            ./manage.py collectstatic --noinput

            if [ -z "$GUNICORN_WORKERS" ]; then
                GUNICORN_WORKERS="$RECOMMENDED_NUM_WORKERS"
            fi

            exec gunicorn $GUNICORN_ARGS -b 0.0.0.0:8000 -w $GUNICORN_WORKERS --access-logfile - wsgi
        fi
    fi
else
    exec $@
fi
