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
import utils
from BackendHandler import BackendHandler, IotaHandler, OrionHandler, PersistenceHandler
from BackendHandler import annotate_status

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
    annotate_status(device_list, service=utils.get_allowed_service(request.headers['authorization']))
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
    if 'protocol' not in device_data.keys() or len(device_data['protocol']) == 0:
        return utils.formatResponse(400, 'missing protocol')

    try:
        service = utils.get_allowed_service(request.headers['authorization'])
        protocolHandler = IotaHandler(service=service)
        subsHandler = PersistenceHandler(service=service)
    except (AttributeError, KeyError):
        return utils.formatResponse(400, 'device has missing fields')
    except (ValueError):
        return utils.formatResponse(304, 'missing authorization info')

    # virtual devices are currently managed (i.e. created on orion) by orchestrator
    device_type = "virtual"
    if device_data['protocol'] != "virtual":
        device_type = "device"
        if not protocolHandler.create(device_data):
            return utils.formatResponse(500, 'failed to configure device')

    device_data['created'] = time()
    device_data['updated'] = time()
    device_data['persistence'] = subsHandler.create(device_data['id'], device_type)
    collection.insert_one(device_data.copy())
    result = {'message': 'device created', 'device': device_data}
    return make_response(json.dumps(result))

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
        protocolHandler = IotaHandler(service=service)
        subsHandler = PersistenceHandler(service=service)
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
        protocolHandler = IotaHandler(service=service)
        subsHandler = PersistenceHandler(service=service)
    except AttributeError:
        return utils.formatResponse(400, 'given device information is missing mandatory fields')

    if not protocolHandler.update(device_data):
        return utils.formatResponse(500, 'failed to update device configuration')

    subsHandler.remove(old_device['persistence'])
    device_data['persistence'] = subsHandler.create(device_data['id'])
    device_data['updated'] = time()
    collection.replace_one({'id' : deviceid}, device_data)
    result = {'message': 'device updated', 'device': device_data}
    return make_response(json.dumps(result))

@device.route('/device/query', methods=['GET'])
def find_device():
    collection = get_mongo_collection(request.headers['authorization'])
    stored_device = collection.find_one(request.args, {"_id" : False, 'persistence': False})
    if stored_device is None:
        return utils.formatResponse(404, 'given device was not found')

    return make_response(json.dumps(stored_device), 200)
