from flask import Blueprint, request, jsonify, make_response

from DeviceManager.conf import CONFIG
from DeviceManager.Logger import Log

from DeviceManager.app import app

from DeviceManager.SerializationModels import parse_payload, load_attrs
from DeviceManager.SerializationModels import log_schema
from DeviceManager.utils import format_response, HTTPRequestError, get_pagination

logger = Blueprint('log', __name__)
LOG = Log()

class LoggerHandler:
    
    def _init_(self):
        pass
    
    @staticmethod
    def update_log_level(level):
        """
        Update the log level of device manager.

        :param level: Receive a string containing the new log level.
        :raises HTTPRequestError: If no authorization token was provided (no
        tenant was informed) or the request body contains some error.
        """

        LOG.update_log_level(level.upper())
        
        return True
    
    @staticmethod
    def get_log_level():
        """
        Fetches the log level configured.

        :return A JSON containing the log level.
        :rtype JSON
        """

        result = {
            'level': LOG.get_log_level()
        }

        return result


@logger.route('/log', methods=['PUT'])
def flask_update_log_level():
    try:
        content_type = request.headers.get('Content-Type')
        data_request = request.data

        _, json_payload = parse_payload(content_type, data_request, log_schema)
        LoggerHandler.update_log_level(json_payload['level'])

        return make_response('', 200)

    except HTTPRequestError as error:
        if isinstance(error.message, dict):
            return make_response(jsonify(error.message), error.error_code)
        return format_response(error.error_code, error.message)

@logger.route('/log', methods=['GET'])
def flask_get_log_level():
    result = LoggerHandler.get_log_level()

    return make_response(jsonify(result), 200)

app.register_blueprint(logger)
