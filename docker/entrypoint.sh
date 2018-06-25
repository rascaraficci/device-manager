#!/bin/sh

command=${1:-start}

TIMEOUT=${GUNICORN_TIMEOUT:-30}

migrate () {
    export FLASK_APP=DeviceManager/main.py
    flask db upgrade
    unset FLASK_APP
}

stamp () {
    export FLASK_APP=DeviceManager/main.py
    flask db stamp 6beff7876a3a
    unset FLASK_APP
}

if [ ${command} = 'start' ]; then
    flag=0
    retries=0
    max_retries=5
    sleep_time=5

    echo "Waiting for DB to come up"
    python docker/waitForDb.py -w ${sleep_time} -r ${max_retries}
    if [ $? -ne 0 ]; then
        echo "Could not connect to DB, shutting down!"
        exit 1
    fi
    echo "Finished waiting for DB"

    while [ ${flag} -eq 0 ]; do
        if [ ${retries} -eq ${max_retries} ]; then
            echo Executed ${retries} retries, aborting
            exit 1
        fi
        echo gunicorn timeout is ${TIMEOUT}
        exec gunicorn DeviceManager.main:app \
                  --bind 0.0.0.0:5000 \
                  --reload -R \
                  --timeout ${TIMEOUT} \
                  --access-logfile - \
                  --log-file - \
                  --env PYTHONUNBUFFERED=1 -k gevent 2>&1

        if [ $? -eq 0 ]; then
            flag=1
        else
            echo "Cannot start application, retying in ${sleep_time} seconds..."
            sleep ${sleep_time}
            retries=$((retries + 1))
        fi
    done
elif [ ${command} = 'migrate' ] ; then
    migrate
elif [ ${command} = '020_stamp' ] ; then
    stamp
fi
