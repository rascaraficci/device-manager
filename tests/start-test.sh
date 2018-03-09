#!/bin/bash
python ./docker/waitForDb.py

for i in {1..10} ; do
  curl -sS -o /dev/null "http://device-manager:5000"
  status=$?
  if [[ "$status" == "0" ]] ; then
    /opt/node_modules/.bin/dredd
    exit $?
  fi
  sleep 2
done

echo "Service under test timed out."
exit 1
