#!/bin/bash

set -x
docker build -t dojot/device-manager ../
docker build -t dredd/test -f tests/Dockerfile ../
docker-compose -p test -f ../tests/docker-compose.yaml up -d kafka data-broker postgres device-manager device-manager-redis postgres-users
docker-compose -p test -f ../tests/docker-compose.yaml run --rm test-runne