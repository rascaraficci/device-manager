import json
import os
from flask import Flask
from flask import request
from flask import make_response
from flask_cors import CORS, cross_origin
import pymongo
from pymongo import MongoClient

db_client = None
db_server = "mongo-db"
db_port = 27017
db_devices = None

def init_database():
    global db_client, db_server, db_port, db_devices
    # Check if mongod is running
    db_client = MongoClient(db_server, db_port)
    db_devices = db_client.iot_devices.devices
    db_devices.create_index([('id', pymongo.ASCENDING)], unique=True)

def remove_icons(deviceid):
    if os.path.isfile('./icons/{}.svg'.format(deviceid)):
        os.remove('./icons/{}.svg'.format(deviceid))

init_database()
app = Flask(__name__)
CORS(app)

def formatResponse(status, message=None):
    payload = None
    if message:
        payload = json.dumps({ 'message': message, 'status': status})
    elif status >= 200 and status < 300:
        payload = json.dumps({ 'message': 'ok', 'status': status})
    else:
        payload = json.dumps({ 'message': 'Request failed', 'status': status})

    return make_response(payload, status);


@app.route('/devices', methods=['GET'])
def get_devices():
    deviceList = []
    for d in db_devices.find({}, {'_id': False}):
        deviceList.append(d)

    all_devices = { "devices" : deviceList}
    resp = make_response(json.dumps(all_devices), 200)
    return resp

@app.route('/devices', methods=['POST'])
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

@app.route('/devices/<deviceid>', methods=['GET'])
def get_device(deviceid):
    global db_devices

    device = db_devices.find_one({'id' : deviceid}, {"_id" : False})
    if device is None:
        return formatResponse(404, 'Given device was not found')

    return make_response(json.dumps(device), 200)

@app.route('/devices/<deviceid>', methods=['DELETE'])
def remove_device(deviceid):
    global db_devices

    result = db_devices.delete_one({'id' : deviceid})
    if result.deleted_count < 1:
        return formatResponse(404, 'Given device was not found')

    remove_icons(deviceid)
    return formatResponse(200)

@app.route('/devices/<deviceid>', methods=['PUT'])
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

@app.route('/devices/<deviceid>/icon', methods=['PUT', 'GET', 'DELETE'])
def manage_icon(deviceid):

    device = db_devices.find_one({'id' : deviceid}, {"_id" : False})
    if device is None:
        return formatResponse(404, 'Given device was not found')

    if request.method == 'PUT':
        icon_file = request.files['icon']
        # For now just svg
        icon_filename = './icons/{}.svg'.format(deviceid)
        icon_file.save(icon_filename)
        if ('has_icon' not in device.keys()) or (device["has_icon"] == False):
            device["has_icon"] = True
            db_devices.replace_one({'id' : deviceid}, device)
        return formatResponse(201)
    elif request.method == 'GET':
        if os.path.isfile('./icons/{}.svg'.format(deviceid)):
            icon_file = open('./icons/{}.svg'.format(deviceid), 'r')
            icon_str = icon_file.read()
            resp = make_response(icon_str, 200)
            # For now just svg
            resp.headers['Content-Type'] = 'image/svg+xml'
            return resp
        else:
            return formatResponse(204, "Given template has no icon assigned")
    elif request.method == 'DELETE':
        remove_icons(deviceid)
        device["has_icon"] = False
        db_devices.replace_one({'id' : deviceid}, device)
        return formatResponse(200)

    return formatResponse(400, "Invalid request type")


if __name__ == '__main__':
    init_database()
    app.run()
