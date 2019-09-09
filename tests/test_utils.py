import pytest
import json
import unittest

from flask import Flask
from DeviceManager.utils import format_response, get_pagination, get_allowed_service, decrypt, retrieve_auth_token
from DeviceManager.utils import HTTPRequestError

from .token_test_generator import generate_token


class Request:
    def __init__(self, data):
        self.headers = data['headers']
        self.args = data['args']
        self.data = data['body']


class TestUtils(unittest.TestCase):

    app = Flask(__name__)

    def test_format_response(self):
        with self.app.test_request_context():
            result = format_response(200, 'Unity test of message formatter')
            self.assertEqual(result.status, '200 OK')
            self.assertEqual(json.loads(result.response[0])[
                             'message'], 'Unity test of message formatter')

            result = format_response(202)
            self.assertEqual(result.status, '202 ACCEPTED')
            self.assertEqual(json.loads(result.response[0])['message'], 'ok')

            result = format_response(404)
            self.assertEqual(result.status, '404 NOT FOUND')
            self.assertEqual(json.loads(result.response[0])[
                             'message'], 'Request failed')

    def test_get_pagination(self):

        args = {'page_size': 10,'page_num': 1}
        req = {'headers': {'authorization': generate_token()},'args': args,'body': ''}

        page, per_page = get_pagination(Request(req))
        self.assertEqual(page, 1)
        self.assertEqual(per_page, 10)

        with self.assertRaises(HTTPRequestError):
            args = {'page_size': 10,'page_num': 0}
            req = {'headers': {'authorization': generate_token()},'args': args,'body': ''}
            page, per_page = get_pagination(Request(req))

        with self.assertRaises(HTTPRequestError):
            args = {'page_size': 0,'page_num': 2}
            req = {'headers': {'authorization': generate_token()},'args': args,'body': ''}
            page, per_page = get_pagination(Request(req))

    def test_get_allowed_service(self):
        token = generate_token()

        with self.assertRaises(ValueError):
            get_allowed_service(None)
        
        result = get_allowed_service(token)
        self.assertIsNotNone(result)
        self.assertEqual(result, 'admin')

        with self.assertRaises(ValueError):
            get_allowed_service('Is.Not_A_Valid_Token')


    def test_decrypt(self):
        result = decrypt(b"\xa97\xa4o\xba\xddx\xe0\xe9\x8f\xe2\xc4V\x85\xf7'")
        self.assertEqual(result, b'')

        with self.assertRaises(ValueError):
            result = decrypt('12345678')

    def test_retrieve_auth_token(self):
        token = generate_token()
        req = {'headers': {'authorization': token},'args': '','body': ''}

        result = retrieve_auth_token(Request(req))
        self.assertIsNotNone(result)
        self.assertEqual(result, token)

        with self.assertRaises(HTTPRequestError):
            req = {'headers': {},'args': '','body': ''}
            result = retrieve_auth_token(Request(req))
