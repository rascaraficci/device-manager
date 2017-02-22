import json
import os
from flask import Flask
from flask import request
from flask import make_response
from flask import Blueprint
import pymongo
from utils import CollectionManager, formatResponse

device = Blueprint('device', __name__)

collection = CollectionManager('device_management').getCollection('devices')
# TODO: this sounds like collection initialization/deployment
collection.create_index([('id', pymongo.ASCENDING)], unique=True)

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
        device_data = json.loads(request.data)

    # sanity checks
    if 'id' not in device_data.keys():
        return formatResponse(400, 'missing id')

    if collection.find_one({'id' : device_id}):
        return formatResponse(400, 'device already registered')

    collection.insert_one(device_data.copy())
    return formatResponse(200)

@device.route('/device/<deviceid>', methods=['GET'])
def get_device(deviceid):
    device = collection.find_one({'id' : deviceid}, {"_id" : False})
    if device is None:
        return formatResponse(404, 'Given device was not found')

    return make_response(json.dumps(device), 200)

@device.route('/device/<deviceid>', methods=['DELETE'])
def remove_device(deviceid):
    result = collection.delete_one({'id' : deviceid})
    if result.deleted_count < 1:
        return formatResponse(404, 'Given device was not found')

    return formatResponse(200)

@device.route('/device/<deviceid>', methods=['PUT'])
def update_device(deviceid):
    if request.mimetype == 'application/x-www-form-urlencoded':
        device_data = request.form
    elif request.mimetype == 'application/json':
        device_data = json.loads(request.data)

    if 'id' not in device_data.keys():
        device_data["id"] = deviceid

    result = collection.replace_one({'id' : deviceid}, device_data)
    if result.matched_count != 1:
        return formatResponse(404, 'Given device was not found')

    return formatResponse(200)
