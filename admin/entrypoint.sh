#!/bin/sh

while ! nc -z db 5432; do
  sleep 0.1
done

./manage.py migrate

if [ "$#" = 0 ]; then
    if [ -z "$GUNICORN_WORKERS" ]; then
        GUNICORN_WORKERS="$(python -c 'import multiprocessing as m; print(max(m.cpu_count() // 2, 1))')"
    fi

    GUNICORN_ARGS="-w $GUNICORN_WORKERS"
    if [ "$DEBUG" = "1" ]; then
        GUNICORN_ARGS="$GUNICORN_ARGS --reload"
    fi

    exec gunicorn $GUNICORN_ARGS -b 0.0.0.0:8000 carb.wsgi
else
    exec $@
fi
