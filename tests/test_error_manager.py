import pytest
import json
import unittest
from unittest.mock import Mock, MagicMock, patch, call
from flask import Flask

from DeviceManager.ErrorManager import not_found, internal_error

class TestErrorManager(unittest.TestCase):

    app = Flask(__name__)

    def test_not_found_endpoint(self):
        with self.app.test_request_context():
            result = not_found(Mock())
            self.assertEqual(result.status, '404 NOT FOUND')
            self.assertEqual(json.loads(result.response[0])[
                             'msg'], 'Invalid endpoint requested')

    def test_internal_error(self):
        with self.app.test_request_context():
            result = internal_error(Mock())
            self.assertEqual(result.status, '500 INTERNAL SERVER ERROR')
            self.assertEqual(json.loads(result.response[0])[
                             'msg'], 'Internal Error')
