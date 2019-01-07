Internal messages
=================

There are some messages that are published by DeviceManager through Kafka.
These messages are notifications of device management operations, and they can
be consumed by any component interested in them, such as IoT agents.

.. list-table:: Kafka messages
   :header-rows: 1

   * - Event
     - Service
     - Message type
   * - Device creation
     - dojot.device-manager.device
     - `Creation message`_
   * - Device update
     - dojot.device-manager.device
     - `Update message`_
   * - Device removal
     - dojot.device-manager.device
     - `Removal message`_
   * - Device actuation
     - dojot.device-manager.device
     - `Actuation message`_
   * - Template update
     - dojot.device-manager.device
     - `Template update message`_


Creation message
----------------

This message is published whenever a new device is created.
Its payload is a simple JSON:

.. code-block:: json

  {
    "event": "create",
    "data": {
        "label": "device",
        "id": "56b7b1",
        "created": "2019-01-07T12:21:22.016175+00:00",
        "templates": [
            1, 2, 3
        ],
        "attrs": {
            "1": [
                {
                    "label": "a",
                    "id": 11,
                    "template_id": "1",
                    "type": "dynamic",
                    "created": "2019-01-07T12:20:55.032796+00:00",
                    "value_type": "string"
                },
                {
                    "label": "b",
                    "id": 12,
                    "template_id": "1",
                    "type": "static",
                    "created": "2019-01-07T12:20:55.033423+00:00",
                    "value_type": "string",
                    "static_value": "b-attr value!"
                }
            ],
            "2": [
                {
                    "label": "c",
                    "id": 13,
                    "template_id": "2",
                    "type": "dynamic",
                    "created": "2019-01-07T12:20:55.031381+00:00",
                    "value_type": "blingbling"
                }
            ],
            "3": [
                {
                    "label": "d",
                    "id": 14,
                    "template_id": "3",
                    "type": "dynamic",
                    "created": "2019-01-07T12:20:55.032172+00:00",
                    "value_type": "string"
                }
            ]
        }
    },
    "meta": {
        "service": "admin"
    }
  }

And its attributes are:

- *event* (string): "create"
- *meta*: Meta information about the message

  - *service* (string): Tenant associated to this device

- *data*: device data structure

  - *id* (string): Device ID
  - *attrs*: Device attributes. This field is as described in :doc:`./concepts`


Update message
--------------

This message is published whenever a new device is updated.
Its payload looks very similar to device creation:

.. code-block:: json

    {
      "event": "update",
      "meta": {
        "service": "admin"
      },
      "data": {
        "id": "efac",
        "label" : "Device 1",
        "templates" : [ 1, 2, 3],
        "attrs" : {
            "1": [
                {
                    "label": "a",
                    "id": 11,
                    "template_id": "1",
                    "type": "dynamic",
                    "created": "2019-01-07T12:20:55.032796+00:00",
                    "value_type": "string"
                },
                {
                    "label": "b",
                    "id": 12,
                    "template_id": "1",
                    "type": "static",
                    "created": "2019-01-07T12:20:55.033423+00:00",
                    "value_type": "string",
                    "static_value": "new b-attr value!"
                }
            ],
            "2": [
                {
                    "label": "c",
                    "id": 13,
                    "template_id": "2",
                    "type": "dynamic",
                    "created": "2019-01-07T12:20:55.031381+00:00",
                    "value_type": "blingbling"
                }
            ],
            "3": [
                {
                    "label": "d",
                    "id": 14,
                    "template_id": "3",
                    "type": "dynamic",
                    "created": "2019-01-07T12:20:55.032172+00:00",
                    "value_type": "string"
                }
            ]

        },
        "created" : "2018-02-06T10:43:40.890330+00:00"
      }
    }


- *event* (string): "update"
- *meta*: Meta information about the message

  - *service* (string): Tenant associated to this device

- *data*: device new data structure

  - *id* (string): ID of the device being updated
  - *attrs*: Device attributes. This field is as described in :doc:`./concepts`


Removal message
---------------

This message is published whenever a device is removed.
Its payload is:

.. code-block:: json

    {
      "event": "remove",
      "meta": {
        "service": "admin"
      },
      "data": {
        "id": "efac"
      }
    }


- *event* (string): "remove"
- *meta*: Meta information about the message

  - *service* (string): Tenant associated to this device

- *data*: device data

  - *id* (string): ID of the device being removed


Actuation message
-----------------

This message is published whenever a device must be configured.
The payload is:

.. code-block:: json

  {
    "event": "actuate",
    "meta": {
      "service": "admin"
    },
    "data" : {
      "id" : "efac",
      "attrs": {
        "reset" : 1,
        "step-motor" : "+45"
      }
    }
  }


- *event* (string): "actuate"
- *meta*: Meta information about the message

  - *service* (string): Tenant associated to this device

This message should be forwarded to the device. It can contain more attributes
than the ones specified by DeviceManager. For instance, a thermostat could be
configured with the following message:

.. code-block:: json

  {
    "event": "actuate",
    "meta": {
      "service": "admin"
    },
    "data" : {
      "id" : "efac",
      "attrs": {
        "target_temperature" : 23.5
      }
    }
  }

The attribute actually used by the device would be "target_temperature" so that
it can adjust correctly the temperature. It's up to the receiver of this
message (an IoT agent, for instance) to properly send the configuration to the
device.


Template update message
-----------------------

This message is published whenever a template gets updated. It contains all the
affected devices and the new model for that template. Important thing to
remember: no message is sent to update *each device*.

Its payload looks like:

.. code-block:: json

  {
    "event": "template.update",
    "data": {
        "affected": [
            "9c6f77"
        ],
        "template": {
            "label": "SuperTemplate",
            "id": 1,
            "created": "2019-01-07T12:03:47.051392+00:00",
            "attrs": [
                {
                    "label": "a",
                    "id": 3,
                    "template_id": "1",
                    "type": "dynamic",
                    "created": "2019-01-07T12:03:47.055768+00:00",
                    "value_type": "string"
                },
                {
                    "label": "b",
                    "id": 4,
                    "template_id": "1",
                    "type": "dynamic",
                    "created": "2019-01-07T12:03:47.056419+00:00",
                    "value_type": "string"
                },
                {
                    "label": "c",
                    "id": 6,
                    "template_id": "1",
                    "type": "dynamic",
                    "created": "2019-01-07T12:11:42.971507+00:00",
                    "value_type": "string"
                }
            ]
        }
    },
    "meta": {
        "service": "admin"
    }
  }


- *event* (string): "template.update"
- *data*:

  - *affected*: list of devices affected by this template update.
  - *template*: new template definition

    - *label*: new template label
    - *id*: template id
    - *created*: timestamp for template update
    - *attrs*: Device attributes. This field is as described in
               :doc:`./concepts`

- *meta*: Meta information about the message

  - *service* (string): Tenant associated to this device
