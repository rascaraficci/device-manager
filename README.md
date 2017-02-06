DeviceManager
=============

# Requirements
 - flask (installed with 'pip install flask')

# How to run
$ export FLASK_APP=./device-manager.py
$ flask run [--port=PORT, --host=0.0.0.0]

Or just
$ python ./device-manager.py

# Using curl to manage devices

## Creating device

 - curl -X POST http://0:5000/devices --data "device-id=dev003" --data "name=thermometer03" --data "location=entrance" --data "purchase-date=02.02.17"
 - curl -X POST http://0:5000/devices --header 'Content-Type:application/json' --data '{ "device-id" : "dev002", "name": "barometer-01"}'

## Retrieving device

 - curl -X GET http://0:5000/devices
 - curl -X GET http://0:5000/devices/dev002

## Updating device info

 - curl -X PUT http://0:5000/devices/dev003 --data "name=thermometer01" --data "location=hallway"

## Deleting device
This will also remove any associated icon

 - curl -X DELETE http://0:5000/devices/dev003

## Uploading and removing icons

 - curl -X PUT http://0:5000/devices/dev002/icon -F "icon=@sample-icons/icon.svg"
 - curl -X DELETE http://0:5000/devices/dev002/icon

