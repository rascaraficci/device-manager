Internal messages
=================

These notifications are sent by DeviceManager through Kafka.


.. list-table:: Kafka messages
   :header-rows: 1

   * - Event
     - Topic
     - Message type
   * - Device creation
     - dojot.device-manager.device
     - Creation message
   * - Device update
     - dojot.device-manager.device
     - Update message
   * - Device removal
     - dojot.device-manager.device
     - Removal message
   * - Device configuration
     - dojot.device-manager.device
     - Configuration message


Creation messages
-----------------

This message is broadcasted whenever a new device is created.

- *event* (string): "create"
- *meta*: Meta information about the message

  - *service* (string): Tenant associated to this device

- *data*: device data structure

  - *id* (string): Device ID
  - *attrs*: Device attributes. This field is as described in :doc:`./concepts`


Update messages
---------------

This message is broadcasted whenever a new device is created.

- *event* (string): "update"
- *meta*: Meta information about the message

  - *service* (string): Tenant associated to this device

- *data*: device new data structure

  - *id* (string): ID of the device being updated
  - *attrs*: Device attributes. This field is as described in :doc:`./concepts`


Removal messages
----------------

This message is broadcasted whenever a new device is created.

- *event* (string): "remove"
- *meta*: Meta information about the message

  - *service* (string): Tenant associated to this device

- *data*: device data

  - *id* (string): ID of the device being removed


Configure messages
------------------

This message is broadcasted whenever a new device is created.

- *event* (string): "configure"
- *meta*: Meta information about the message

  - *service* (string): Tenant associated to this device
  - *id* (string): ID of the device to be configured
  - *topic* (string): MQTT topic to be used for device configuration

Any other parameter will be sent to the device.
