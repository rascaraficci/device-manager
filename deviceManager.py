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
from utils import CollectionManager, formatResponse, get_allowed_service

device = Blueprint('device', __name__)

db = CollectionManager('device_management')


def get_mongo_collection(token):
    """
        Returns a pymongo collection object pointing to the service-enabled
        collection to be used

        :param token: JWT token received
        :returns: pymongo collection object
        :raises ValueError: Invalid token received
    """
    service = get_allowed_service(token)
    collection = db("dev_service_%s" % service)
    return collection



class IotaHandler:
    """ Abstracts interaction with iotagent-json for MQTT device management """
    # TODO: this should be configurable (via file or environment variable)
    def __init__(self, device, baseUrl='http://iotagent:4041/iot', service='devm'):
        self.device = device
        self.baseUrl = baseUrl
        self.service = service
        self._headers = {
            'Fiware-service': service,
            'Fiware-servicePath': '/',
            'Content-Type':'application/json',
            'cache-control': 'no-cache'
        }

        self._config = {
            'device_id': self.device['label'],   # TODO this makes demoing way easier
            'entity_type': service,
            'entity_name': self.device['label'],
            'attributes': self.device['attrs']
        }

    def create(self):
        """ Returns boolean indicating device creation success. """

        try:
            svc = json.dumps({
                "services": [{
                    "resource": "devm",
                    "apikey": self.service,
                    "entity_type": self.service
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

    def remove(self, label):
        """ Returns boolean indicating device removal success. """

        try:
            response = requests.delete(self.baseUrl + '/devices/' + label,
                                    headers=self._headers)
            return response.status_code >= 200 and response.status_code < 300
        except ConnectionError:
            return False

    def update(self):
        """ Returns boolean indicating device update success. """

        try:
            response = requests.put(self.baseUrl + '/devices/' + self._config['label'],
                                    headers=self._headers, data=json.dumps(self._config))
            return response.status_code >= 200 and response.status_code < 300
        except ConnectionError:
            return False

# Temporarily create a subscription to persist device data
# TODO this must be revisited in favor of a orchestrator-based solution
class PersistenceHandler:
    # TODO: this should be configurable (via file or environment variable)
    def __init__(self, device, service='devm', baseUrl='http://orion:1026/v1/contextSubscriptions', targetUrl="http://sth:8666/notify"):
        self.device = device
        self.baseUrl = baseUrl
        self.targetUrl = targetUrl
        self.service = service
        self._headers = {
            'Fiware-service': service,
            'Fiware-servicePath': '/',
            'Content-Type':'application/json',
            'cache-control': 'no-cache'
        }

    def create(self):
        """ Returns subscription id on success. """

        try:
            svc = json.dumps({
                "entities": [{
                    "type": self.service,
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
    collection = get_mongo_collection(request.headers['authorization'])
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
    collection = get_mongo_collection(request.headers['authorization'])
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
        service = get_allowed_service(request.headers['authorization'])
        protocolHandler = IotaHandler(device_data, service=service)
        subsHandler = PersistenceHandler(device_data, service=service)
    except (AttributeError, KeyError):
        return formatResponse(400, 'device has missing fields')
    except (ValueError):
        return formatResponse(304, 'missing authorization info')

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
    collection = get_mongo_collection(request.headers['authorization'])
    device = collection.find_one({'id' : deviceid}, {"_id" : False})
    if device is None:
        return formatResponse(404, 'given device was not found')

    return make_response(json.dumps(device), 200)

@device.route('/device/<deviceid>', methods=['DELETE'])
def remove_device(deviceid):
    collection = get_mongo_collection(request.headers['authorization'])
    # sanity check
    device = collection.find_one({'id': deviceid})
    if not device:
        return formatResponse(404, 'given device was not found')

    try:
        service = get_allowed_service(request.headers['authorization'])
        protocolHandler = IotaHandler(device, service=service)
        subsHandler = PersistenceHandler(device, service=service)
    except AttributeError:
        return formatResponse(500, 'given device information is corrupted')

    if protocolHandler.remove(device['label']):
        subsHandler.remove(device['persistence'])
        result = collection.delete_one({'id' : deviceid})
        return formatResponse(200)
    else:
        return formatResponse(500, 'failed to remove device')


@device.route('/device/<deviceid>', methods=['PUT'])
def update_device(deviceid):
    collection = get_mongo_collection(request.headers['authorization'])
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

    old_device = collection.find_one({'id': deviceid})
    if not old_device:
        return formatResponse(404, 'given device was not found')

    try:
        service = get_allowed_service(request.headers['authorization'])
        protocolHandler = IotaHandler(device_data, service=service)
        subsHandler = PersistenceHandler(device_data, service=service)
    except AttributeError:
        return formatResponse(400, 'given device information is missing mandatory fields')

    # TODO use device id instead of name as id for fiware backend
    if not protocolHandler.remove(old_device['label']) and subsHandler.remove(old_device['persistence']):
        return formatResponse(500, 'failed to update device configuration (removal)')
    if not protocolHandler.create():
        return formatResponse(500, 'failed to update device configuration (creation)')

    device_data['persistence'] = subsHandler.create()
    device_data['updated'] = time()
    collection.replace_one({'id' : deviceid}, device_data)
    return formatResponse(200)
