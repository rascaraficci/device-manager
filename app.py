import json
import os
from flask import Flask
from flask_cors import CORS, cross_origin
from templateManager import template
from deviceManager import device

app = Flask(__name__)
app.register_blueprint(device)
app.register_blueprint(template)
CORS(app)

if __name__ == '__main__':
    app.run()
