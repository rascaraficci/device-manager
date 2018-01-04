# DeviceManager

[![License badge](https://img.shields.io/badge/license-GPL-blue.svg)](https://opensource.org/licenses/GPL-3.0)
[![Docker badge](https://img.shields.io/docker/pulls/dojot/iotagent-json.svg)](https://hub.docker.com/r/dojot/device-manager/)

The DeviceManager handles all operations related to creation, retrieval, update and deletion of devices in dojot. For more information
on that, check [this file](./docs/concepts.md).

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

If you really need to run DeviceManager as a standalone process (without dojot's wonderful [docker-compose](https://github.com/dojot/docker-compose)), you can execute these commands:

```shell
python setup.py develop
gunicorn device-manager.app:app
```

Keep in mind that running a standalone instance of DeviceManager misses a lot of security checks (such as user identity checks, proper multi-tenancy validations, and so on). In particular, every request sent to DeviceManager needs an access token, which should be retrived from [auth](https://github.com/dojot/auth) component. In the examples listed in this README, you can generate one by yourself (for now, DeviceManager doesn't check if the token is actually valid for that user - they are verified by auth and the API gateway) but this method might not work in the future as more strict token checks are implemented in DeviceManager.

## Using curl to manage devices

In order to manage devices using DeviceManager, you can use curl (or Postman, if you prefer) to do that.
DeviceManager listens to requests on port 5000. All endpoints are documented [here](https://dojot.github.io/device-manager/apis.html).

__IMPORTANT: All examples consider that the requests are being sent directly to DeviceManager. Visit [dojot's documentation](http://dojotdocs.readthedocs.io/en/latest/user_guide.html) to check the endpoints for all services (including DeviceManager's)__

### Quick example #1: creating a template

This command will send a request to create a template.

```bash
curl -X POST http://localhost:5000/template \
     -H 'Authorization: Bearer JWT' \
     -H 'Content-Type:application/json' \
     -d ' {
  "label": "DeviceTemplate",
  "attrs": [
    {
      "label": "temperature",
      "type": "dynamic",
      "value_type": "float"
    },
    {
      "label": "pressure",
      "type": "dynamic",
      "value_type": "float"
    }
  ]
}'
```

This request will return:

```json
{
  "result": "ok",
  "template": {
    "created": "2018-01-03T17:58:17.429588+00:00",
    "attrs": [
      {
        "template_id": "1",
        "created": "2018-01-03T17:58:17.498937+00:00",
        "label": "temperature",
        "value_type": "float",
        "type": "dynamic",
        "id": 1
      },
      {
        "template_id": "1",
        "created": "2018-01-03T17:58:17.500199+00:00",
        "label": "pressure",
        "value_type": "float",
        "type": "dynamic",
        "id": 2
      }
    ],
    "id": 1,
    "label": "DeviceTemplate"
  }
}
```

Note that this new template has ID 1. This must be used in device creation.

### Quick example #2: retrieving templates

The following request will list all configured templates:

```bash
curl -X DELETE http://localhost:5000/template/1 -H 'Authorization: Bearer JWT'
```

Which gives us:

```json
{
  "templates": [
    {
      "created": "2018-01-03T17:58:17.429588+00:00",
      "attrs": [
        {
          "template_id": "1",
          "created": "2018-01-03T17:58:17.498937+00:00",
          "label": "temperature",
          "value_type": "float",
          "type": "dynamic",
          "id": 1
        },
        {
          "template_id": "1",
          "created": "2018-01-03T17:58:17.500199+00:00",
          "label": "pressure",
          "value_type": "float",
          "type": "dynamic",
          "id": 2
        }
      ],
      "id": 1,
      "label": "DeviceTemplate"
    }
  ],
  "pagination": {
    "has_next": false,
    "next_page": null,
    "total": 1,
    "page": 1
  }
}
```

### Quick example #2: creating a device

The following request creates a new device using the template created in first example.

```bash
curl -X POST http://localhost:5000/device \
-H 'Authorization: Bearer JWT' \
-H 'Content-Type:application/json' \
-d ' {
  "templates": [
    "1"
  ],
  "label": "sensor-1",
  "protocol": "MQTT"
}'
```

The answer is:

```json
{
  "device": {
    "templates": [
      1
    ],
    "created": "2018-01-03T18:00:07.272652+00:00",
    "attrs": {
      "1": [
        {
          "template_id": "1",
          "created": "2018-01-03T17:58:17.498937+00:00",
          "label": "temperature",
          "value_type": "float",
          "type": "dynamic",
          "id": 1
        },
        {
          "template_id": "1",
          "created": "2018-01-03T17:58:17.500199+00:00",
          "label": "pressure",
          "value_type": "float",
          "type": "dynamic",
          "id": 2
        }
      ]
    },
    "id": "3e8d",
    "label": "sensor-1"
  },
  "message": "device created"
}
```

### Quick example #2: removing a device

This request will remove the device created in the last example:

```bash
curl -X DELETE http://localhost:5000/device/3e8d -H 'Authorization: Bearer JWT'
```

The answer is

```json
{
  "removed_device": {
    "templates": [
      1
    ],
    "created": "2018-01-03T18:00:07.272652+00:00",
    "attrs": {
      "1": [
        {
          "template_id": "1",
          "created": "2018-01-03T17:58:17.498937+00:00",
          "label": "temperature",
          "value_type": "float",
          "type": "dynamic",
          "id": 1
        },
        {
          "template_id": "1",
          "created": "2018-01-03T17:58:17.500199+00:00",
          "label": "pressure",
          "value_type": "float",
          "type": "dynamic",
          "id": 2
        }
      ]
    },
    "id": "3e8d",
    "label": "sensor-1"
  },
  "result": "ok"
}
```

Removing a template is very similar:

```bash
curl -X DELETE http://localhost:5000/template/1 -H 'Authorization: Bearer JWT'
```

Which gives us:

```json
{
  "removed": {
    "created": "2018-01-03T17:58:17.429588+00:00",
    "attrs": [
      {
        "template_id": "1",
        "created": "2018-01-03T17:58:17.498937+00:00",
        "label": "temperature",
        "value_type": "float",
        "type": "dynamic",
        "id": 1
      },
      {
        "template_id": "1",
        "created": "2018-01-03T17:58:17.500199+00:00",
        "label": "pressure",
        "value_type": "float",
        "type": "dynamic",
        "id": 2
      }
    ],
    "id": 1,
    "label": "DeviceTemplate"
  },
  "result": "ok"
}
```

### Creating tokens for tests

Just a quick reminder: you should use the [auth](https://github.com/dojot/auth) component for that. But you could enconding
a simple JSON into a base64 string:

```json
{"service" : "admin"}
```

which is: eyJzZXJ2aWNlIiA6ICJhZG1pbiJ9Cgo=

You're welcome.

Concatenate it with dummy strings in both beginning and ending, such as "a.eyJzZXJ2aWNlIiA6ICJhZG1pbiJ9Cgo=.b".

ATTENTION: this method will only work if DeviceManager is accessed directly. If used together with other components, there are going to be 'unauthorized' failures - use [auth](https://github.com/dojot/auth) to generate a valid token.