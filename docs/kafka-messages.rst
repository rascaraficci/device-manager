Internal messages
=================

There are some messages that are published by DeviceManager through Kafka.
These messages are notifications of device management operations, and they can
be consumed by any component interested in them, such as IoT agents.

.. list-table:: Kafka messages
   :header-rows: 1

   * - Event
     - Topic
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
   * - Device configuration
     - dojot.device-manager.device
     - `Configuration message`_


Creation message
----------------

This message is published whenever a new device is created.
Its payload is a simple JSON:

.. code-block:: json

    {
      "event": "create",
      "meta": {
        "service": "admin"
      },
      "data": {
        "id": "efac",
        "attrs" : {

        }
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
        "attrs" : {

        }
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


Configuration message
---------------------

This message is published whenever a device must be configured.
The payload is:

.. code-block:: json

  {
    "event": "configure",
    "meta": {
      "topic": "/admin/cafe/attrs",
      "id": "cafe"
    },
    "data": {
      "id": "cafe"
    },
    "device-attr1": "value"
  }


- *event* (string): "configure"
- *meta*: Meta information about the message

  - *service* (string): Tenant associated to this device
  - *id* (string): ID of the device to be configured
  - *topic* (string): MQTT topic to be used for device configuration

This message should be forwarded to the device. It can contain more attributes than
the ones specified by DeviceManager. For instance, a thermostat could be configured
with the following message:

.. code-block:: json

  {
    "event": "configure",
    "meta": {
      "topic": "/admin/cafe/attrs",
      "id": "cafe"
    },
    "data": {
      "id": "cafe"
    },
    "target-temperature": "27"
  }

The attribute actually used by the device would be "target-temperature" so that
it can adjust correctly the temperature. It's up to the receiver of this message
to properly send the configuration to the device.