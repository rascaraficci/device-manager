import json
import os
from flask import Flask
from flask import request
from flask import make_response
from flask import Blueprint
import pymongo
import requests
from requests import ConnectionError
from utils import CollectionManager, formatResponse

device = Blueprint('device', __name__)

collection = CollectionManager('device_management').getCollection('devices')
# TODO: this sounds like collection initialization/deployment
collection.create_index([('id', pymongo.ASCENDING)], unique=True)

class IotaHandler:
    """ Abstracts interaction with iotagent-json for MQTT device management """
    def __init__(self, device, baseUrl='http://iotagent:4041/iot'):
        self.device = device
        self.baseUrl = baseUrl
        self._headers = {
            'Fiware-service': 'devm',   # TODO: this should be user id
            'Fiware-servicePath': '/',
            'Content-Type':'application/json',
            'cache-control': 'no-cache'
        }

        self._config = {
            'device_id': self.device['id'],
            'entity_type': 'device',    # TODO: is it always going to be the same?
            'entity_name': self.device['label'],
            'attributes': self.device['attrs']
        }

    def create(self):
        """ Returns boolean indicating device creation success. """

        payload = { 'devices': [self._config]}
        try:
            response = requests.post(self.baseUrl + '/devices', headers=self._headers,
                                     data=json.dumps(payload))
            return response.status_code >= 200 and response.status_code < 300
        except ConnectionError:
            return False

    def remove(self):
        """ Returns boolean indicating device removal success. """

        try:
            response = requests.delete(self.baseUrl + '/devices/' + self._config['device_id'],
                                    headers=self._headers)
            return response.status_code >= 200 and response.status_code < 300
        except ConnectionError:
            return False

    def update(self):
        """ Returns boolean indicating device update success. """

        try:
            response = requests.put(self.baseUrl + '/devices/' + self._config['device_id'],
                                    headers=self._headers, data=json.dumps(self._config))
            return response.status_code >= 200 and response.status_code < 300
        except ConnectionError:
            return False


@device.route('/device', methods=['GET'])
def get_devices():
    deviceList = []
    for d in collection.find({}, {'_id': False}):
        deviceList.append(d)

    all_devices = { "devices" : deviceList}
    resp = make_response(json.dumps(all_devices), 200)
    return resp

@device.route('/device', methods=['POST'])
def create_device():
    device_id = ""
    device_data = {}
    if request.mimetype == 'application/x-www-form-urlencoded':
        device_data = request.form
    elif request.mimetype == 'application/json':
        try:
            device_data = json.loads(request.data)
        except ValueError:
            return formatResponse(400, 'invalid device configuration given')
    else:
        return formatResponse(400, 'unknown request format')

    # sanity checks
    if 'id' not in device_data.keys():
        return formatResponse(400, 'missing id')

    if 'protocol' not in device_data.keys():
        return formatResponse(400, 'missing protocol')

    if collection.find_one({'id' : device_id}):
        return formatResponse(400, 'device already registered')

    try:
        protocolHandler = IotaHandler(device_data)
    except AttributeError:
        return formatResponse(400, 'device has missing fields')

    if protocolHandler.create():
        collection.insert_one(device_data.copy())
        return formatResponse(200)
    else:
        return formatResponse(500, 'failed to configure device')

@device.route('/device/<deviceid>', methods=['GET'])
def get_device(deviceid):
    device = collection.find_one({'id' : deviceid}, {"_id" : False})
    if device is None:
        return formatResponse(404, 'given device was not found')

    return make_response(json.dumps(device), 200)

@device.route('/device/<deviceid>', methods=['DELETE'])
def remove_device(deviceid):

    # sanity check
    device = collection.find_one({'id': deviceid})
    if not device:
        return formatResponse(404, 'given device was not found')

    try:
        protocolHandler = IotaHandler(device)
    except AttributeError:
        return formatResponse(500, 'given device information is corrupted')

    if protocolHandler.remove():
        result = collection.delete_one({'id' : deviceid})
        return formatResponse(200)
    else:
        return formatResponse(500, 'failed to remove device')


@device.route('/device/<deviceid>', methods=['PUT'])
def update_device(deviceid):
    if request.mimetype == 'application/x-www-form-urlencoded':
        device_data = request.form
    elif request.mimetype == 'application/json':
        try:
            device_data = json.loads(request.data)
        except ValueError:
            return formatResponse(400, 'invalid device configuration given')
    else:
        return formatResponse(400, 'unknown request format')


    if 'id' not in device_data.keys():
        device_data["id"] = deviceid

    if not collection.find_one({'id': deviceid}):
        return formatResponse(404, 'given device was not found')

    try:
        protocolHandler = IotaHandler(device_data)
    except AttributeError:
        return formatResponse(400, 'given device information is missing mandatory fields')


    if protocolHandler.update():
        collection.replace_one({'id' : deviceid}, device_data)
        return formatResponse(200)
    else:
        return formatResponse(500, 'failed to update device configuration')
