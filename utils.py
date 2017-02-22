import json
import pymongo
from flask import make_response
from pymongo import MongoClient

class CollectionManager:
    def __init__(self, database, server='mongodb', port=27017):
        self.client = None
        self.collection = None
        self.database = database
        self.server = server
        self.port = port

    def getDB(self):
        if not self.client:
            self.client = MongoClient(self.server, self.port)
        return self.client[self.database]

    def getCollection(self, collection):
        return self.getDB()[collection]

    def __call__(self, collection):
        return self.getCollection(collection)

def formatResponse(status, message=None):
    payload = None
    if message:
        payload = json.dumps({ 'message': message, 'status': status})
    elif status >= 200 and status < 300:
        payload = json.dumps({ 'message': 'ok', 'status': status})
    else:
        payload = json.dumps({ 'message': 'Request failed', 'status': status})

    return make_response(payload, status);
