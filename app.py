import json
import os
from flask import Flask
from flask_cors import CORS, cross_origin
import pymongo
from pymongo import MongoClient
from templateManager import template, init_template_database
from deviceManager import device, init_device_database

init_device_database()
init_template_database()

app = Flask(__name__)
app.register_blueprint(device)
app.register_blueprint(template)
CORS(app)

if __name__ == '__main__':
    app.run()
