import json
import os
from flask import Flask
from flask import request
from flask import make_response
from flask import Blueprint
import pymongo
from utils import CollectionManager, formatResponse

collection = CollectionManager('device_management').getCollection('templates')
# TODO: this sounds like collection initialization/deployment
collection.create_index([('id', pymongo.ASCENDING)], unique=True)

template = Blueprint('template', __name__)

def remove_icons(deviceid):
    if os.path.isfile('./icons/{}.svg'.format(deviceid)):
        os.remove('./icons/{}.svg'.format(deviceid))

@template.route('/template', methods=['GET'])
def get_templates():
    templateList = []
    for d in collection.find({}, {'_id': False}):
        templateList.append(d)

    all_templates = { "templates" : templateList}
    return make_response(json.dumps(all_templates), 200)

@template.route('/template', methods=['POST'])
def create_template():
    template_id = ""
    template_data = {}
    if request.mimetype == 'application/x-www-form-urlencoded':
        template_data = request.form
    elif request.mimetype == 'application/json':
        template_data = json.loads(request.data)

    # sanity checks
    if 'id' not in template_data.keys():
        return formatResponse(400, 'missing id')

    if collection.find_one({'id' : template_id}):
        return formatResponse(400, 'template already registered')

    collection.insert_one(template_data.copy())
    return formatResponse(200)

@template.route('/template/<templateid>', methods=['GET'])
def get_template(templateid):
    template = collection.find_one({'id' : templateid}, {"_id" : False})
    if template is None:
        return formatResponse(404, 'Given template was not found')

    return make_response(json.dumps(template), 200)

@template.route('/template/<templateid>', methods=['DELETE'])
def remove_template(templateid):
    result = collection.delete_one({'id' : templateid})
    if result.deleted_count < 1:
        return formatResponse(404, 'Given template was not found')

    remove_icons(templateid)
    return formatResponse(200)

@template.route('/template/<templateid>', methods=['PUT'])
def update_template(templateid):
    template_data = None
    if request.mimetype == 'application/x-www-form-urlencoded':
        template_data = request.form
    elif request.mimetype == 'application/json':
        template_data = json.loads(request.data)

    if 'id' not in template_data.keys():
        template_data["id"] = templateid

    print "will update "
    print template_data
    result = collection.replace_one({'id' : templateid}, template_data)
    if result.matched_count != 1:
        return formatResponse(404, 'Given template was not found')

    return formatResponse(200)

@template.route('/template/<templateid>/icon', methods=['PUT', 'GET', 'DELETE'])
def manage_icon(templateid):
    template = collection.find_one({'id' : templateid}, {"_id" : False})
    if template is None:
        return formatResponse(404, 'Given template was not found')

    if request.method == 'PUT':
        icon_file = request.files['icon']
        # For now just svg
        icon_filename = './icons/{}.svg'.format(templateid)
        icon_file.save(icon_filename)
        if ('has_icon' not in template.keys()) or (template["has_icon"] == False):
            template["has_icon"] = True
            collection.replace_one({'id' : templateid}, template)
        return formatResponse(201)
    elif request.method == 'GET':
        if os.path.isfile('./icons/{}.svg'.format(templateid)):
            icon_file = open('./icons/{}.svg'.format(templateid), 'r')
            icon_str = icon_file.read()
            resp = make_response(icon_str, 200)
            # For now just svg
            resp.headers['Content-Type'] = 'image/svg+xml'
            return resp
        else:
            return formatResponse(204, "Given template has no icon assigned")
    elif request.method == 'DELETE':
        remove_icons(templateid)
        template["has_icon"] = False
        collection.replace_one({'id' : templateid}, template)
        return formatResponse(200)

    return formatResponse(400, "Invalid request type")
