import json
import os
from flask import Flask
from flask import request
from flask import make_response
from flask_cors import CORS, cross_origin
import pymongo
from pymongo import MongoClient

devices = {}
db_client = 0
db_server = "mongo-db"
db_port = 27017
db_devices = 0

def init_database():
    global db_client, db_server, db_port, db_devices
    # Check if mongod is running
    db_client = MongoClient(db_server, db_port)
    db_devices = db_client.iot_devices.devices
    db_devices.create_index([('id', pymongo.ASCENDING)], unique=True)

def read_from_database():
    global devices
    devices_list = db_client.iot_devices.devices
    for device in devices_list.find({}, {'_id': False}):
        devices[device['id']] = device
        print('Device: {}'.format(device))

init_database()
read_from_database()
app = Flask(__name__)
CORS(app)

@app.route('/devices', methods=['GET'])
def get_devices():
    all_devices = { "devices" : devices.values()}
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

    if 'id' not in device_data.keys():
        resp = make_response('missing id', 400)
        return resp
    device_id = device_data['id']

    if request.method == 'POST':
        if device_id in devices.keys():
            resp = make_response('device already registered', 400)
            return resp;

    devices[device_id] = device_data

    # Persisting new device
    db_devices.insert_one(device_data.copy())

    return make_response('ok', 201)

@app.route('/devices/<deviceid>', methods=['GET', 'DELETE'])
def get_device(deviceid):
    global devices, db_devices
    resp = make_response('ok', 200)
    # Device must be already registered
    if deviceid not in devices.keys():
        resp = make_response('not found', 404)
        return resp;

    if request.method == 'GET':
        resp = make_response(json.dumps(devices[deviceid]), 200)
    elif request.method == 'DELETE':
        # Remove from devices map
        devices = { key:devices[key] for key in devices if key != deviceid }
        # Remove icon
        if os.path.isfile('./icons/{}.svg'.format(deviceid)):
            os.remove('./icons/{}.svg'.format(deviceid))
        # Remove from database
        db_devices.remove({'id' : deviceid})
    return resp

@app.route('/devices/<deviceid>', methods=['PUT'])
def update_device(deviceid):
    resp = make_response('ok', 200)
    # Device must be already registered
    if deviceid not in devices.keys():
        resp = make_response('not found', 404)
        return resp;

    if request.mimetype == 'application/x-www-form-urlencoded':
        device_data = request.form
    elif request.mimetype == 'application/json':
        device_data = json.loads(request.data)

    devices[deviceid] = device_data

    # Persisting new device
    db_devices.insert_one(device_data)

    return make_response('ok', 200)

@app.route('/devices/<deviceid>/icon', methods=['PUT', 'GET', 'DELETE'])
def manage_icon(deviceid):
    if deviceid not in devices.keys():
        resp = make_response('not found', 404)
        return resp;

    if request.method == 'PUT':
        icon_file = request.files['icon']
        # For now just svg
        icon_filename = './icons/{}.svg'.format(deviceid)
        icon_file.save(icon_filename)
        return make_response('ok', 201)
    elif request.method == 'GET':
        if os.path.isfile('./icons/{}.svg'.format(deviceid)):
            icon_file = open('./icons/{}.svg'.format(deviceid), 'r')
            icon_str = icon_file.read()
            resp = make_response(icon_str, 200)
            # For now just svg
            resp.headers['Content-Type'] = 'image/svg+xml'
            return resp
        else:
            resp = make_response("ok", 204)
            return resp
    elif request.method == 'DELETE':
        if os.path.isfile('./icons/{}.svg'.format(deviceid)):
            os.remove('./icons/{}.svg'.format(deviceid))
        return make_response('ok', 200)



if __name__ == '__main__':
    init_database()
    read_from_database()
    app.run()
