import pytest
import json
import unittest

from DeviceManager.LoggerHandler import LoggerHandler, flask_update_log_level, flask_get_log_level
from DeviceManager.utils import HTTPRequestError
from DeviceManager.SerializationModels import log_schema 

from flask import Flask
from unittest.mock import Mock, MagicMock, patch

class TestLoggerHandler(unittest.TestCase):

    app = Flask(__name__)

    def test_update_valid_level_log(self):
        self.assertTrue(LoggerHandler.update_log_level("info"), "")
        with self.assertRaises(HTTPRequestError):   
            LoggerHandler.update_log_level("teste")

    def test_get_actual_level_log(self):
        level = LoggerHandler.get_log_level()
        self.assertIsNotNone(level)
        
    def test_endpoint_get_log(self):
        with self.app.test_request_context():
            result = flask_get_log_level()
            self.assertEqual(result.status, '200 OK')
            self.assertEqual(json.loads(result.response[0])[
                             'level'], 'INFO')

    def test_endpoint_update_log(self):
        with self.app.test_request_context():
            result = flask_update_log_level()
            self.assertEqual(result.status, '400 BAD REQUEST')
            self.assertEqual(json.loads(result.response[0])[
                             'message'], 'Payload must be valid JSON, and Content-Type set accordingly')
         