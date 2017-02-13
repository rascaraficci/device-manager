import json
import os
from flask import Flask
from flask import request
from flask import make_response
from flask import Blueprint
import pymongo
from pymongo import MongoClient

db_client = None
db_server = "mongo-db"
db_port = 27017
db_devices = None

device = Blueprint('device', __name__)

def init_device_database():
    global db_client, db_server, db_port, db_devices
    # Check if mongod is running
    db_client = MongoClient(db_server, db_port)
    db_devices = db_client.iot_devices.devices
    db_devices.create_index([('id', pymongo.ASCENDING)], unique=True)

def formatResponse(status, message=None):
    payload = None
    if message:
        payload = json.dumps({ 'message': message, 'status': status})
    elif status >= 200 and status < 300:
        payload = json.dumps({ 'message': 'ok', 'status': status})
    else:
        payload = json.dumps({ 'message': 'Request failed', 'status': status})

    return make_response(payload, status);


@device.route('/device', methods=['GET'])
def get_devices():
    deviceList = []
    for d in db_devices.find({}, {'_id': False}):
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

    if db_devices.find_one({'id' : device_id}):
        return formatResponse(400, 'device already registered')

    db_devices.insert_one(device_data.copy())
    return formatResponse(200)

@device.route('/device/<deviceid>', methods=['GET'])
def get_device(deviceid):
    global db_devices

    device = db_devices.find_one({'id' : deviceid}, {"_id" : False})
    if device is None:
        return formatResponse(404, 'Given device was not found')

    return make_response(json.dumps(device), 200)

@device.route('/device/<deviceid>', methods=['DELETE'])
def remove_device(deviceid):
    global db_devices

    result = db_devices.delete_one({'id' : deviceid})
    if result.deleted_count < 1:
        return formatResponse(404, 'Given device was not found')

    return formatResponse(200)

@device.route('/device/<deviceid>', methods=['PUT'])
def update_device(deviceid):
    global db_devices

    if request.mimetype == 'application/x-www-form-urlencoded':
        device_data = request.form
    elif request.mimetype == 'application/json':
        device_data = json.loads(request.data)

    if 'id' not in device_data.keys():
        device_data["id"] = deviceid

    result = db_devices.replace_one({'id' : deviceid}, device_data)
    if result.matched_count != 1:
        return formatResponse(404, 'Given device was not found')

    return formatResponse(200)
