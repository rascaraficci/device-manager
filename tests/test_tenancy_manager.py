import pytest
import json
import unittest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.sql import exists

from DeviceManager.TenancyManager import install_triggers, create_tenant, init_tenant, list_tenants

from alchemy_mock.mocking import AlchemyMagicMock, UnifiedAlchemyMagicMock

class TestTenancyManager(unittest.TestCase):

    def test_install_triggers(self):
        db_mock = AlchemyMagicMock()
        self.assertIsNone(install_triggers(db_mock, 'admin'))

    def test_create_tenant(self):
        db_mock = AlchemyMagicMock()
        self.assertIsNone(create_tenant('admin', db_mock))

    def test_init_tenant(self):
        db_mock = Mock(return_value=None)
        self.assertIsNone(init_tenant('admin', db_mock))

    def test_list_tenants(self):
        db_mock = AlchemyMagicMock()
        self.assertFalse(list_tenants(db_mock))
