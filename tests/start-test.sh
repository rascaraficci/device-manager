#!/bin/bash
python ./docker/waitForDb.py
/opt/node_modules/.bin/dredd
