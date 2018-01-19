# DeviceManager

[![License badge](https://img.shields.io/badge/license-GPL-blue.svg)](https://opensource.org/licenses/GPL-3.0)
[![Docker badge](https://img.shields.io/docker/pulls/dojot/iotagent-json.svg)](https://hub.docker.com/r/dojot/device-manager/)

The DeviceManager handles all operations related to creation, retrieval, update and deletion of devices in dojot. For more information
on that, check [this file](./docs/concepts.rst).

## Dependencies

DeviceManager has the following dependencies:

- flask (including flask_sqlalchemy)
- psycopg2
- marshmallow
- requests
- gunicorn
- gevent
- json-logging-py
- kakfa-python

But you won't need to worry about installing any of these - they are automatically installed when starting DeviceManager.
There must be, though, a postgres instance accessible by DeviceManager.

## How to run

If you really need to run DeviceManager as a standalone process (without dojot's wonderful [docker-compose](https://github.com/dojot/docker-compose)), we suggest using the minimal compose
file available under `docker/compose.yml`. That contains only the set of external systems (postgres
and kafka) that are used by device manager to implement its features. To have this minimal environment
running, please:

```shell
# spin up local copies of remote dependencies
docker-compose -f local/compose.yml -p devm up -d
# Builds devm container (this may take a while)
docker build -f Dockerfile -t local/devicemanager .
# Runs devm manually, using the infra that's been just created
docker run --rm -it --network devm_default local/devicemanager
#
# Hitting ^C will actually kill device-manager's process and the container
#
```

"Ok, but I ***really*** want to run device manager on my machine - no docker no nothing."

 You can execute the following commands (it's just what runs in the container, actually - check
 `docker/entrypoint.sh` and `Dockerfile`).

```shell
# install dependencies locally (may take a while)
python setup.py develop

export DBHOST="postgres ip/hostname goes here"
export KAFKA_HOST="kafka ip/hostname goes here"

docker/waitForDb.py
gunicorn DeviceManager.main:app -k gevent --logfile - --access-logfile -
```

Do notice that all those external infra (kafka and postgres) will have to be up and running still.
At a minimum, please remember to configure the two environment variables above, to their real values
(specially if they are both `localhost`).

Keep in mind that running a standalone instance of DeviceManager misses a lot of security checks
(such as user identity checks, proper multi-tenancy validations, and so on). In particular,
every request sent to DeviceManager needs an access token, which should be retrived from
[auth](https://github.com/dojot/auth) component. In the examples listed in this README, you
can generate one by yourself (for now, DeviceManager doesn't check if the token is actually
valid for that user - they are verified by auth and the API gateway) but this method might not
work in the future as more strict token checks are implemented in DeviceManager.

## How to use

There are a few examples on how to use DeviceManager in [this page](./docs/using-device-manager.rst).
