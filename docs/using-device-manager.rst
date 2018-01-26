Using DeviceManager
===================

Using DeviceManager is indeed simple: create a template with attributes
and then create devices using that template. That’s it. This page will
show how to do that.

All examples in this page consider that all dojot’s components are up
and running (check `the
documentation <http://dojotdocs.readthedocs.io/>`_ for how to do that).
All request will include a ``${JWT}`` variable - this was retrieved from
`auth <https://github.com/dojot/auth>`_ component.

Creating templates and devices
------------------------------

Right off the bat, let’s retrieve a token from ``auth``:

.. code-block:: bash

    curl -X POST http://localhost:8000/auth \
    -H 'Content-Type:application/json' \
    -d '{"username": "admin", "passwd" : "admin"}'

.. code-block:: json

    {
      "jwt": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIU..."
    }

This token will be stored in ``bash ${JWT}`` bash variable, referenced
in all requests.

.. ATTENTION::
  Every request made with this token will be valid only for
  the tenant (user “service”) associated with this token. For instance,
  listing created devices will return only those devices which were
  created using this tenant.

--------------

A template is, simply put, a model from which devices can be created.
They can be merged to build a single device (or a set of devices). It is
created by sending a HTTP request to DeviceManager:

.. code-block:: bash

    curl -X POST http://localhost:8000/template \
    -H "Authorization: Bearer ${JWT}" \
    -H 'Content-Type:application/json' \
    -d ' {
      "label": "SuperTemplate",
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
        },
        {
          "label": "model",
          "type": "static",
          "value_type" : "string",
          "static_value" : "SuperTemplate Rev01"
        }
      ]
    }'

Supported ``type`` values are “dynamic”, “static” and “meta”. Supported
``value_types`` are “float”, “geo” (for georeferenced data), “string”,
“integer”.

The answer is:

.. code-block:: json

    {
      "result": "ok",
      "template": {
        "created": "2018-01-05T15:41:54.803052+00:00",
        "attrs": [
          {
            "template_id": "1",
            "created": "2018-01-05T15:41:54.840116+00:00",
            "label": "temperature",
            "value_type": "float",
            "type": "dynamic",
            "id": 1
          },
          {
            "template_id": "1",
            "created": "2018-01-05T15:41:54.882169+00:00",
            "label": "pressure",
            "value_type": "float",
            "type": "dynamic",
            "id": 2
          },
          {
            "static_value": "SuperTemplate Rev01",
            "created": "2018-01-05T15:41:54.883507+00:00",
            "label": "model",
            "value_type": "string",
            "type": "static",
            "id": 3,
            "template_id": "1"
          }
        ],
        "id": 1,
        "label": "SuperTemplate"
      }
    }

Let’s create one more template, so that we can see what happens when two
templates are merged.

.. code-block:: bash

    curl -X POST http://localhost:8000/template \
    -H "Authorization: Bearer ${JWT}" \
    -H 'Content-Type:application/json' \
    -d ' {
      "label": "ExtraTemplate",
      "attrs": [
        {
          "label": "gps",
          "type": "dynamic",
          "value_type": "geo"
        }
      ]
    }'

Which results in:

.. code-block:: json

    {
      "result": "ok",
      "template": {
        "created": "2018-01-05T15:47:02.993965+00:00",
        "attrs": [
          {
            "template_id": "2",
            "created": "2018-01-05T15:47:02.995541+00:00",
            "label": "gps",
            "value_type": "geo",
            "type": "dynamic",
            "id": 4
          }
        ],
        "id": 2,
        "label": "ExtraTemplate"
      }
    }

Let’s check all templates we’ve created so far.

.. code-block:: bash

    curl -X GET http://localhost:8000/template -H "Authorization: Bearer ${JWT}"

.. code-block:: json

    {
      "templates": [
        {
          "created": "2018-01-05T15:41:54.803052+00:00",
          "attrs": [
            {
              "template_id": "1",
              "created": "2018-01-05T15:41:54.840116+00:00",
              "label": "temperature",
              "value_type": "float",
              "type": "dynamic",
              "id": 1
            },
            {
              "template_id": "1",
              "created": "2018-01-05T15:41:54.882169+00:00",
              "label": "pressure",
              "value_type": "float",
              "type": "dynamic",
              "id": 2
            },
            {
              "static_value": "SuperTemplate Rev01",
              "created": "2018-01-05T15:41:54.883507+00:00",
              "label": "model",
              "value_type": "string",
              "type": "static",
              "id": 3,
              "template_id": "1"
            }
          ],
          "id": 1,
          "label": "SuperTemplate"
        },
        {
          "created": "2018-01-05T15:47:02.993965+00:00",
          "attrs": [
            {
              "template_id": "2",
              "created": "2018-01-05T15:47:02.995541+00:00",
              "label": "gps",
              "value_type": "geo",
              "type": "dynamic",
              "id": 4
            }
          ],
          "id": 2,
          "label": "ExtraTemplate"
        }
      ],
      "pagination": {
        "has_next": false,
        "next_page": null,
        "total": 1,
        "page": 1
      }
    }

Now devices can be created using these two templates. Such request would
be:

.. code-block:: bash

    curl -X POST http://localhost:8000/device \
    -H "Authorization: Bearer ${JWT}" \
    -H 'Content-Type:application/json' \
    -d ' {
      "templates": [
        "1",
        "2"
      ],
      "label": "device"
    }'

The result is:

.. code-block:: json

    {
      "device": {
        "templates": [
          1,
          2
        ],
        "created": "2018-01-05T17:33:31.605748+00:00",
        "attrs": {
          "1": [
            {
              "template_id": "1",
              "created": "2018-01-05T15:41:54.840116+00:00",
              "label": "temperature",
              "value_type": "float",
              "type": "dynamic",
              "id": 1
            },
            {
              "template_id": "1",
              "created": "2018-01-05T15:41:54.882169+00:00",
              "label": "pressure",
              "value_type": "float",
              "type": "dynamic",
              "id": 2
            },
            {
              "static_value": "SuperTemplate Rev01",
              "created": "2018-01-05T15:41:54.883507+00:00",
              "label": "model",
              "value_type": "string",
              "type": "static",
              "id": 3,
              "template_id": "1"
            }
          ],
          "2": [
            {
              "template_id": "2",
              "created": "2018-01-05T15:47:02.995541+00:00",
              "label": "gps",
              "value_type": "geo",
              "type": "dynamic",
              "id": 4
            }
          ]
        },
        "id": "b7bd",
        "label": "device"
      },
      "message": "device created"
    }

Notice how the resulting device is structured: it has a list of related
templates (``template`` attribute) and each of its attributes are
separated by template ID: ``temperature``, ``pressure`` and ``model``
are inside attribute ``1`` (ID of the first created template) and
``gps`` is inside attribute ``2`` (ID of the second template). The new
device ID can be found in the ``id`` attribute, which is ``b7bd``.

A few considerations must be made:

-  If the templates used to compose this new device had attributes with
   the same name, an error would be generated and the device would not
   be created.
-  If any of the related templates are removed, all its attributes will
   also be removed from the devices that were created using it. So be
   careful.

Let’s retrieve this new device:

.. code-block:: bash

    curl -X GET http://localhost:8000/device -H "Authorization: Bearer ${JWT}"

This request will list all created devices for the tenant.

.. code-block:: json

    {
      "pagination": {
        "has_next": false,
        "next_page": null,
        "total": 1,
        "page": 1
      },
      "devices": [
        {
          "templates": [
            1,
            2
          ],
          "created": "2018-01-05T17:33:31.605748+00:00",
          "attrs": {
            "1": [
              {
                "template_id": "1",
                "created": "2018-01-05T15:41:54.840116+00:00",
                "label": "temperature",
                "value_type": "float",
                "type": "dynamic",
                "id": 1
              },
              {
                "template_id": "1",
                "created": "2018-01-05T15:41:54.882169+00:00",
                "label": "pressure",
                "value_type": "float",
                "type": "dynamic",
                "id": 2
              },
              {
                "static_value": "SuperTemplate Rev01",
                "created": "2018-01-05T15:41:54.883507+00:00",
                "label": "model",
                "value_type": "string",
                "type": "static",
                "id": 3,
                "template_id": "1"
              }
            ],
            "2": [
              {
                "template_id": "2",
                "created": "2018-01-05T15:47:02.995541+00:00",
                "label": "gps",
                "value_type": "geo",
                "type": "dynamic",
                "id": 4
              }
            ]
          },
          "id": "b7bd",
          "label": "device"
        }
      ]
    }

Removing templates and devices
------------------------------

Removing templates and devices is also very simple. Let’s remove the
device created previously:

.. code-block:: bash

    curl -X DELETE http://localhost:8000/device/b7bd -H "Authorization: Bearer ${JWT}"

.. code-block:: json

    {
      "removed_device": {
        "templates": [
          1,
          2
        ],
        "created": "2018-01-05T17:33:31.605748+00:00",
        "attrs": {
          "1": [
            {
              "template_id": "1",
              "created": "2018-01-05T15:41:54.840116+00:00",
              "label": "temperature",
              "value_type": "float",
              "type": "dynamic",
              "id": 1
            },
            {
              "template_id": "1",
              "created": "2018-01-05T15:41:54.882169+00:00",
              "label": "pressure",
              "value_type": "float",
              "type": "dynamic",
              "id": 2
            },
            {
              "static_value": "SuperTemplate Rev01",
              "created": "2018-01-05T15:41:54.883507+00:00",
              "label": "model",
              "value_type": "string",
              "type": "static",
              "id": 3,
              "template_id": "1"
            }
          ],
          "2": [
            {
              "template_id": "2",
              "created": "2018-01-05T15:47:02.995541+00:00",
              "label": "gps",
              "value_type": "geo",
              "type": "dynamic",
              "id": 4
            }
          ]
        },
        "id": "b7bd",
        "label": "device"
      },
      "result": "ok"
    }

Removing templates is also simple:

.. code-block:: bash

    curl -X DELETE http://localhost:8000/template/1 -H "Authorization: Bearer ${JWT}"

.. code-block:: json

    {
      "removed": {
        "created": "2018-01-05T15:41:54.803052+00:00",
        "attrs": [
          {
            "template_id": "1",
            "created": "2018-01-05T15:41:54.840116+00:00",
            "label": "temperature",
            "value_type": "float",
            "type": "dynamic",
            "id": 1
          },
          {
            "template_id": "1",
            "created": "2018-01-05T15:41:54.882169+00:00",
            "label": "pressure",
            "value_type": "float",
            "type": "dynamic",
            "id": 2
          },
          {
            "static_value": "SuperTemplate Rev01",
            "created": "2018-01-05T15:41:54.883507+00:00",
            "label": "model",
            "value_type": "string",
            "type": "static",
            "id": 3,
            "template_id": "1"
          }
        ],
        "id": 1,
        "label": "SuperTemplate"
      },
      "result": "ok"
    }

These are the very basic operations performed by DeviceManager. All
operations can be found in `API documentation <api.html>`_.



Sending configuration messages to devices
-----------------------------------------

You can send change any device attribute via DeviceManager. In order to do so, 
first you have to set a template attribute as "configurable". By default, all
attributes are not configurable, i.e., they can't be set or overwritten by
the user (or any other entity for that matter). Let's create a very similar 
template from `Creating templates and devices`_ and call it a 'Thermostat':

.. code-block:: bash

    curl -X POST http://localhost:8000/template \
    -H "Authorization: Bearer ${JWT}" \
    -H 'Content-Type:application/json' \
    -d ' {
      "label": "Thermostat",
      "attrs": [
        {
          "label": "temperature",
          "type": "dynamic",
          "value_type": "float",
          "configurable" : true
        },
        {
          "label": "pressure",
          "type": "dynamic",
          "value_type": "float",
          "configurable" : false
        },
        {
          "label": "model",
          "type": "static",
          "value_type" : "string",
          "static_value" : "Thermostat Rev01"
        }
      ]
    }'


Note that the ``temperature`` attribute now has the ``configurable`` property, 
as well as the ``pressure`` property. The ``model``, once it has no such 
property, it will be considered as not-configurable.

This request should give an answer like this:

.. code-block:: json

    {
      "result": "ok",
      "template": {
        "created": "2018-01-26T15:56:07.070839+00:00",
        "label": "Thermostat",
        "attrs": [
          {
            "created": "2018-01-26T15:56:07.073699+00:00",
            "label": "temperature",
            "value_type": "float",
            "configurable": true,
            "type": "dynamic",
            "id": 10,
            "template_id": "4"
          },
          {
            "created": "2018-01-26T15:56:07.077078+00:00",
            "label": "pressure",
            "value_type": "float",
            "configurable": false,
            "type": "dynamic",
            "id": 11,
            "template_id": "4"
          },
          {
            "static_value": "Thermostat Rev01",
            "created": "2018-01-26T15:56:07.078822+00:00",
            "label": "model",
            "value_type": "string",
            "configurable": false,
            "type": "static",
            "id": 12,
            "template_id": "4"
          }
        ],
        "id": 4
      }
    }

Also note that the ``model`` attribute has ``configurable`` property set as
false.

Creating a device based on it is no different than before:

.. code-block:: bash

  curl -X POST http://localhost:8000/device \
    -H "Authorization: Bearer ${JWT}" \
    -H 'Content-Type:application/json' \
    -d ' {
      "templates": [
        "4"
      ],
      "label": "device"
    }'

This gives back the following data:

.. code-block:: json

  {
    "message": "devices created",
    "devices": [
      {
        "id": "356d",
        "label": "device"
      }
    ]
  }


To send a configuration message to the device, you should send a request like
this:

.. code-block:: bash

    curl -X PUT http://localhost:8000/device/356d/configure \
    -H "Authorization: Bearer ${JWT}" \
    -H 'Content-Type:application/json' \
    -d ' {
        "topic": "/admin/356d/config",
        "attrs": {
            "temperature" : 10.6
        }
    }'

We use the endpoint ``/device/<DEVICEID>/configure`` to send configuration
messages to a particular device. The payload contains two attributes:

- topic: MQTT topic to which the configuration message will be published.
- attrs: All the attributes and their respective values that will be configured
  on the device. The device will receive this part of the payload as
  configuration.

Remember that the attribute must be configurable for this request to succeed.
If not, a message like the following one is returned:

.. code-block:: json

  {
    "status": "some of the attributes are not configurable",
    "attrs": [
      "pressure"
    ]
  }