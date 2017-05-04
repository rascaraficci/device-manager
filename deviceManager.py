"""
    Handles CRUD operations for devices, and their configuration on the
    FIWARE backend
"""

import json
from time import time
from flask import request
from flask import make_response
from flask import Blueprint
import pymongo
import requests
from requests import ConnectionError
import utils

device = Blueprint('device', __name__)
db = utils.CollectionManager('device_management')

def get_mongo_collection(token):
    """
        Returns a pymongo collection object pointing to the service-enabled
        collection to be used

        :param token: JWT token received
        :returns: pymongo collection object
        :raises ValueError: Invalid token received
    """
    service = utils.get_allowed_service(token)
    collection = db("dev_service_%s" % service)
    return collection

class IotaHandler(object):
    """ Abstracts interaction with iotagent-json for MQTT device management """
    # TODO: this should be configurable (via file or environment variable)
    def __init__(self, _device, baseUrl='http://iotagent:4041/iot', service='devm'):
        self.device = _device
        self.baseUrl = baseUrl
        self.service = service
        self._headers = {
            'Fiware-service': service,
            'Fiware-servicePath': '/',
            'Content-Type':'application/json',
            'cache-control': 'no-cache'
        }

    def __get_topic(self):
        topic = ''
        if 'topic' in self.device:
            topic = self.device.topic
        else:
            topic = "/%s/%s/attrs" % (self.service, self.device['id'])

        print "will set topic [%s]" % topic
        return topic

    def __get_config(self):

        # Currently, there's no efficient way (apart from setting extra metadata) to have the
        # context broker store a human-readable label to be associated with an entity (device).
        # Here we use entity_type as a cheap alternative
        return {
            # this is actually consumed by iotagent
            'device_id': self.device['id'],
            # becomes entity type for context broker
            'entity_type': 'device',
            # becomes entity id for context broker
            'entity_name': self.device['id'],
            'attributes': self.device['attrs'],
            # this is actually consumed by iotagent
            'internal_attributes': {
                "attributes" : [
                    {"topic": "tcp:mqtt:%s" % self.__get_topic()}
                ]
            },
            # becomes part of the attribute list on context broker
            'static_attributes': [
                # TODO this should be part of the entity metadata
                {'name': 'user_label', 'type':'string', 'value': self.device['label']}
            ]
        }

    def create(self):
        """ Returns boolean indicating device creation success. """

        try:
            svc = json.dumps({
                "services": [{
                    "resource": "devm",
                    "apikey": self.service,
                    "entity_type": 'device'
                }]
            })
            response = requests.post(self.baseUrl + '/services', headers=self._headers, data=svc)
            if not (response.status_code == 409 or
                    (response.status_code >= 200 and response.status_code < 300)):
                return False
        except ConnectionError:
            return False

        try:
            response = requests.post(self.baseUrl + '/devices', headers=self._headers,
                                     data=json.dumps({'devices':[self.__get_config()]}))
            return response.status_code >= 200 and response.status_code < 300
        except ConnectionError:
            return False

    def remove(self, deviceid):
        """ Returns boolean indicating device removal success. """

        try:
            response = requests.delete(self.baseUrl + '/devices/' + deviceid,
                                       headers=self._headers)
            return response.status_code >= 200 and response.status_code < 300
        except ConnectionError:
            return False

    def update(self):
        """ Returns boolean indicating device update success. """

        config = self.__get_config()
        config.pop('internal_attributes', None) # TODO add support for topic edition on iotagent
        try:
            response = requests.put(self.baseUrl + '/devices/' + self.device['id'],
                                    headers=self._headers, data=json.dumps(config))
            return response.status_code >= 200 and response.status_code < 300
        except ConnectionError:
            return False

# Temporarily create a subscription to persist device data
# TODO this must be revisited in favor of a orchestrator-based solution
class PersistenceHandler(object):
    """
        Abstracts the configuration of subscriptions targeting the default
        history backend (STH)
    """
    # TODO: this should be configurable (via file or environment variable)
    def __init__(self, _device, service='devm',
                 baseUrl='http://orion:1026/v1/contextSubscriptions',
                 targetUrl="http://sth:8666/notify"):
        self.device = _device
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
                    "type": 'device',
                    "isPattern": "false",
                    "id": self.device['id']
                }],
                "reference" : self.targetUrl,
                "duration": "P10Y",
                "notifyConditions": [{"type": "ONCHANGE"}]
            })
            response = requests.post(self.baseUrl, headers=self._headers, data=svc)
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
    """
        Fetches known devices, potentially limited by a given value.
        The ordering might be user-configurable too.
    """
    collection = get_mongo_collection(request.headers['authorization'])
    field_filter = {'_id': False, 'persistence': False}
    if 'limit' in request.args.keys():
        try:
            cursor = collection.find({}, field_filter,
                                     limit=int(request.args['limit']))
        except TypeError:
            return utils.formatResponse(400, 'limit must be an integer value')
    else:
        cursor = collection.find({}, field_filter)

    sort = []
    if 'sortAsc' in request.args.keys():
        sort.append((request.args['sortAsc'], pymongo.ASCENDING))
    if 'sortDsc' in request.args.keys():
        sort.append((request.args['sortDsc'], pymongo.DESCENDING))
    if len(sort) > 0:
        cursor.sort(sort)

    device_list = []
    for dev_it in cursor:
        device_list.append(dev_it)

    all_devices = {"devices" : device_list}
    return make_response(json.dumps(all_devices), 200)

@device.route('/device', methods=['POST'])
def create_device():
    """ Creates and configures the given device (in json) """

    collection = get_mongo_collection(request.headers['authorization'])
    device_data = {}
    if request.mimetype == 'application/x-www-form-urlencoded':
        device_data = request.form
    elif request.mimetype == 'application/json':
        try:
            device_data = json.loads(request.data)
        except ValueError:
            return utils.formatResponse(400, 'Failed to parse payload as JSON')
    else:
        return utils.formatResponse(400, 'unknown request format')

    # TODO this is awful, makes me sad, but for now also makes demoing easier
    # We might want to look into an auto-configuration feature using the service
    # and device name on automate to be able to remove this
    _attempts = 0
    device_data['id'] = ''
    while _attempts < 10 and len(device_data['id']) == 0:
        new_id = utils.create_id()
        if not collection.find_one({'id' : new_id}):
            device_data['id'] = new_id
            break
    if not len(device_data['id']):
        return utils.formatResponse(500, 'failed to generate unique id')

    # sanity checks
    if 'protocol' not in device_data.keys():
        return utils.formatResponse(400, 'missing protocol')

    try:
        service = utils.get_allowed_service(request.headers['authorization'])
        protocolHandler = IotaHandler(device_data, service=service)
        subsHandler = PersistenceHandler(device_data, service=service)
    except (AttributeError, KeyError):
        return utils.formatResponse(400, 'device has missing fields')
    except (ValueError):
        return utils.formatResponse(304, 'missing authorization info')

    if protocolHandler.create():
        device_data['created'] = time()
        device_data['updated'] = time()
        device_data['persistence'] = subsHandler.create()
        collection.insert_one(device_data.copy())
        return utils.formatResponse(200)
    else:
        return utils.formatResponse(500, 'failed to configure device')

@device.route('/device/<deviceid>', methods=['GET'])
def get_device(deviceid):
    collection = get_mongo_collection(request.headers['authorization'])
    stored_device = collection.find_one({'id' : deviceid},
                                        {"_id" : False, 'persistence': False})
    if stored_device is None:
        return utils.formatResponse(404, 'given device was not found')

    return make_response(json.dumps(stored_device), 200)

@device.route('/device/<deviceid>', methods=['DELETE'])
def remove_device(deviceid):
    collection = get_mongo_collection(request.headers['authorization'])
    # sanity check
    old_device = collection.find_one({'id': deviceid})
    if not old_device:
        return utils.formatResponse(404, 'given device was not found')

    try:
        service = utils.get_allowed_service(request.headers['authorization'])
        protocolHandler = IotaHandler(old_device, service=service)
        subsHandler = PersistenceHandler(old_device, service=service)
    except AttributeError:
        return utils.formatResponse(500, 'given device information is corrupted')

    if protocolHandler.remove(deviceid):
        subsHandler.remove(old_device['persistence'])
        collection.delete_one({'id' : deviceid})
        return utils.formatResponse(200)
    else:
        return utils.formatResponse(500, 'failed to remove device')


@device.route('/device/<deviceid>', methods=['PUT'])
def update_device(deviceid):
    collection = get_mongo_collection(request.headers['authorization'])
    if request.mimetype == 'application/x-www-form-urlencoded':
        device_data = request.form
    elif request.mimetype == 'application/json':
        try:
            device_data = json.loads(request.data)
        except ValueError:
            return utils.formatResponse(400, 'Failed to parse payload as JSON')
    else:
        return utils.formatResponse(400, 'unknown request format')

    if 'id' not in device_data.keys():
        device_data["id"] = deviceid

    old_device = collection.find_one({'id': deviceid})
    if not old_device:
        return utils.formatResponse(404, 'given device was not found')

    try:
        service = utils.get_allowed_service(request.headers['authorization'])
        protocolHandler = IotaHandler(device_data, service=service)
        subsHandler = PersistenceHandler(device_data, service=service)
    except AttributeError:
        return utils.formatResponse(400, 'given device information is missing mandatory fields')

    if not protocolHandler.update():
        return utils.formatResponse(500, 'failed to update device configuration')


    # TODO use device id instead of name as id for fiware backend
    # if not (protocolHandler.remove(deviceid)
    #         and subsHandler.remove(old_device['persistence'])):
    #     return utils.formatResponse(500, 'failed to update device configuration (removal)')
    # if not protocolHandler.create():
    #     return utils.formatResponse(500, 'failed to update device configuration (creation)')

    device_data['persistence'] = subsHandler.create()
    device_data['updated'] = time()
    collection.replace_one({'id' : deviceid}, device_data)
    return utils.formatResponse(200)
