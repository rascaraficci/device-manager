import pytest
import json
import unittest
from unittest.mock import Mock, MagicMock, patch


from DeviceManager.DatabaseHandler import MultiTenantSQLAlchemy, before_request

from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy

class TestDatabaseHandler(unittest.TestCase):

    app = Flask(__name__)

    def test_check_binds_multi_tenancy(self):
        self.assertIsNone(MultiTenantSQLAlchemy().check_binds('test_bind_sql_alchemy'))

    def test_choose_tenant_multi_tenancy(self):
        with self.app.test_request_context():
            self.assertIsNone(MultiTenantSQLAlchemy().choose_tenant('test_bind_sql_alchemy'))

    def test_get_engine_multi_tenancy(self):
        with self.app.test_request_context():
            with self.assertRaises(RuntimeError):
                MultiTenantSQLAlchemy().get_engine()

        self.app.config['SQLALCHEMY_BINDS'] = {
            'test_bind_sql_alchemy': 'postgresql+psycopg2://postgres@postgres/dojot_devm',
        }

        sql_alchemy = SQLAlchemy(self.app)
        sql_alchemy.init_app(self.app)

        self.assertIsNotNone(MultiTenantSQLAlchemy().get_engine(self.app, 'test_bind_sql_alchemy'))

    def test_before_request(self):
        with self.app.test_request_context():
            result = before_request()
            self.assertEqual(result.status, '401 UNAUTHORIZED')
            self.assertEqual(json.loads(result.response[0])[
                             'message'], 'No authorization token has been supplied')
                             