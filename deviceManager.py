import json
import os
from time import time
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
    # TODO: this should be configurable (via file or environment variable)
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
            'device_id': self.device['label'],   # TODO this makes demoing way easier
            'entity_type': 'device',    # TODO: is it always going to be the same?
            'entity_name': self.device['label'],
            'attributes': self.device['attrs']
        }

    def create(self):
        """ Returns boolean indicating device creation success. """

        try:
            svc = json.dumps({
                "services": [{
                    "resource": "devm",
                    "apikey": "device",
                    "entity_type": "device"
                }]
            })
            response = requests.post(self.baseUrl + '/services', headers=self._headers, data=svc)
            if not (response.status_code == 409 or
                   (response.status_code >= 200 and response.status_code < 300)):
                return False
        except ConnectionError:
            return False

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

# Temporarily create a subscription to persist device data
# TODO this must be revisited in favor of a orchestrator-based solution
class PersistenceHandler:
    # TODO: this should be configurable (via file or environment variable)
    def __init__(self, device, baseUrl='http://orion:1026/v1/contextSubscriptions', targetUrl="http://sth:8666/notify"):
        self.device = device
        self.baseUrl = baseUrl
        self.targetUrl = targetUrl
        self._headers = {
            'Fiware-service': 'devm',   # TODO: this should be user id
            'Fiware-servicePath': '/',
            'Content-Type':'application/json',
            'cache-control': 'no-cache'
        }

    def create(self):
        """ Returns subscription id on success. """

        try:
            svc = json.dumps({
                "entities": [{
                    "type": "device",
                    "isPattern": "false",
                    "id": self.device['label']
                }],
                "reference" : self.targetUrl,
                "duration": "P10Y",
                "notifyConditions": [{ "type": "ONCHANGE" }]
            })
            response = requests.post(self.baseUrl, headers=self._headers, data=svc)
            print("got result %d" % response.status_code)
            if not (response.status_code == 409 or
                   (response.status_code >= 200 and response.status_code < 300)):
                return None

            # return the newly created subs
            reply = response.json()
            print(reply)
            return reply['subscribeResponse']['subscriptionId']

        except (ConnectionError, ValueError):
            print('error')
            return None

    def remove(self, subsId):
        """ Returns boolean indicating subscription removal success. """

        try:
            response = requests.delete(self.baseUrl + '/' + subsId, headers=self._headers)
            return response.status_code >= 200 and response.status_code < 300
        except ConnectionError:
            return False


@device.route('/device', methods=['GET'])
def get_devices():
    if ('limit' in request.args.keys()):
        try:
            cursor = collection.find({}, {'_id': False}, limit=int(request.args['limit']));
        except TypeError:
            return formatResponse(400, 'limit must be an integer value')
    else:
        cursor = collection.find({}, {'_id': False});

    sort = []
    if 'sortAsc' in request.args.keys():
        sort.append((request.args['sortAsc'], pymongo.ASCENDING))
    if 'sortDsc' in request.args.keys():
        sort.append((request.args['sortDsc'], pymongo.DESCENDING))
    if len(sort) > 0:
        cursor.sort(sort)

    deviceList = []
    for d in cursor:
        deviceList.append(d)

    all_devices = {"devices" : deviceList}
    return make_response(json.dumps(all_devices), 200)

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
            return formatResponse(400, 'Failed to parse payload as JSON')
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
        subsHandler = PersistenceHandler(device_data)
    except (AttributeError, KeyError):
        return formatResponse(400, 'device has missing fields')

    if protocolHandler.create():
        device_data['created'] = time()
        device_data['updated'] = time()
        print('about to subs handle')
        device_data['persistence'] = subsHandler.create()
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
        subsHandler = PersistenceHandler(device)
    except AttributeError:
        return formatResponse(500, 'given device information is corrupted')

    if protocolHandler.remove():
        subsHandler.remove(device['persistence'])
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
            return formatResponse(400, 'Failed to parse payload as JSON')
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
        device_data['updated'] = time()
        collection.replace_one({'id' : deviceid}, device_data)
        return formatResponse(200)
    else:
        return formatResponse(500, 'failed to update device configuration')
