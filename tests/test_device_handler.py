import pytest
import json
import unittest
from unittest.mock import Mock, MagicMock, patch

from DeviceManager.DeviceHandler import DeviceHandler
from DeviceManager.utils import HTTPRequestError
from DeviceManager.DatabaseModels import Device

from .token_test_generator import generate_token

from alchemy_mock.mocking import AlchemyMagicMock, UnifiedAlchemyMagicMock

class TestDeviceHandler(unittest.TestCase):

    @patch('flask_sqlalchemy._QueryProperty.__get__')
    def test_generate_deviceId(self, query_property_getter_mock):
        query_property_getter_mock.return_value.filter_by.return_value.first.return_value = None
        self.assertIsNotNone(DeviceHandler.generate_device_id())

        query_property_getter_mock.return_value.filter_by.return_value.first.return_value = 'existed_device_id'
        with pytest.raises(HTTPRequestError):   
            DeviceHandler.generate_device_id()


    @patch('DeviceManager.DeviceHandler.db')
    def test_get_devices(self, db_mock):
        db_mock.session = UnifiedAlchemyMagicMock()

        db_mock.session.paginate().items = [Device(id=1, label='test_device1')]

        params_query = {'page_number': 5, 'per_page': 1, 'sortBy': None, 'attr':[], 'idsOnly':'false', 'attr_type': [], 'label': 'test_device1'}
        token = generate_token()
        
        result = DeviceHandler.get_devices(token, params_query)

        self.assertIsNotNone(result)
        self.assertTrue(json.dumps(result['devices']))

        params_query = {'page_number': 1, 'per_page': 1, 'sortBy': None, 'attr':[], 'idsOnly':'false', 'attr_type': []}
        result = DeviceHandler.get_devices(token, params_query)
        self.assertTrue(json.dumps(result['devices']))
        self.assertIsNotNone(result)

        params_query = {'page_number': 1, 'per_page': 1, 'sortBy': None, 'attr':['foo=bar'], 'idsOnly':'false', 'attr_type': []}
        result = DeviceHandler.get_devices(token, params_query)
        self.assertTrue(json.dumps(result['devices']))
        self.assertIsNotNone(result)

        params_query = {'sortBy': None, 'attr':[], 'idsOnly':'true', 'attr_type': []}

        with patch.object(DeviceHandler, "get_only_ids", return_value=['4f2b', '1e4a']) as DeviceOnlyIds:
            result = DeviceHandler.get_devices(token, params_query)
            self.assertTrue(json.dumps(result))
            DeviceOnlyIds.assert_called_once()

        params_query = {'page_number': 5, 'per_page': 1, 'sortBy': None, 'attr':[], 'idsOnly':'false', 'attr_type': [], 'label': 'test_device1'}
        result = DeviceHandler.get_devices(token, params_query, True)
        self.assertTrue(json.dumps(result['devices']))
        self.assertIsNotNone(result)

    @patch('DeviceManager.DeviceHandler.db')
    def test_list_devicesId(self, db_mock):
        db_mock.session = AlchemyMagicMock()
        token = generate_token()

        db_mock.session.query(Device.id).all.return_value = ['4f2b', '1e4a']

        result = DeviceHandler.list_ids(token)
        self.assertTrue(json.dumps(result))
        self.assertIsNotNone(result)

    @patch('DeviceManager.DeviceHandler.db')
    @patch('flask_sqlalchemy._QueryProperty.__get__')
    def test_get_device(self, db_mock, query_property_getter_mock):
        db_mock.session = AlchemyMagicMock()
        token = generate_token()

        query_property_getter_mock.filter_by.one.return_value = Device(id=1, label='teste')
        result = DeviceHandler.get_device(token, 'device_id')
        self.assertIsNotNone(result)

    @patch('DeviceManager.DeviceHandler.db')
    @patch('flask_sqlalchemy._QueryProperty.__get__')
    def test_delete_device(self, db_mock, query_property_getter_mock):
        db_mock.session = AlchemyMagicMock()
        token = generate_token()

        with patch.object(DeviceHandler, "verifyInstance", return_value=MagicMock()) as KafkaInstanceMock:
            result = DeviceHandler.delete_device(None, 'device_id', token)
            KafkaInstanceMock.assert_called_once()
            self.assertIsNotNone(result)
            self.assertEqual(result['result'], 'ok')

    @patch('DeviceManager.DeviceHandler.db')
    @patch('flask_sqlalchemy._QueryProperty.__get__')
    def test_delete_all_devices(self, db_mock, query_property_getter_mock):
        db_mock.session = AlchemyMagicMock()
        token = generate_token()

        db_mock.session.query(Device).return_value = [Device(id=1, label='device_label')]
        result = DeviceHandler.delete_all_devices(token)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['result'], 'ok')

    @patch('DeviceManager.DeviceHandler.db')
    @patch('flask_sqlalchemy._QueryProperty.__get__')
    def test_add_template_to_device(self, db_mock, query_property_getter_mock):
        db_mock.session = AlchemyMagicMock()
        token = generate_token()

        query_property_getter_mock.filter_by.one.return_value = Device(id=1, label='device_label')
        result = DeviceHandler.add_template_to_device(token, 'device_id', 'template_id')
        self.assertIsNotNone(result)
        self.assertIsNotNone(result['device'])
        self.assertEqual(result['message'], 'device updated')

    @patch('DeviceManager.DeviceHandler.db')
    @patch('flask_sqlalchemy._QueryProperty.__get__')
    def test_remove_template_to_device(self, db_mock, query_property_getter_mock):
        db_mock.session = AlchemyMagicMock()
        token = generate_token()

        query_property_getter_mock.filter_by.one.return_value = Device(id=1, label='device_label')
        result = DeviceHandler.remove_template_from_device(token, 'device_id', 'template_id')
        self.assertIsNotNone(result)
        self.assertIsNotNone(result['device'])
        self.assertEqual(result['message'], 'device updated')

    @patch('DeviceManager.DeviceHandler.db')
    def test_get_devices_by_templateId(self, db_mock):
        db_mock.session = AlchemyMagicMock()
        token = generate_token()

        params_query = {'page_number': 1, 'per_page': 1}

        db_mock.session.paginate().items = [Device(id=1, label='test_device1')]
        result = DeviceHandler.get_by_template(token, params_query, 'template_id')
        self.assertIsNotNone(result)

    @patch('DeviceManager.DeviceHandler.db')
    #@patch('flask_sqlalchemy._QueryProperty')
    def test_generate_shared_key(self, db_mock):
        db_mock.session = UnifiedAlchemyMagicMock(return_value=Device(id=1, label='test_device1'))
        token = generate_token()

        db_mock.session.query.filter_by('test_device1').one.return_value = UnifiedAlchemyMagicMock(return_value=Device(id=1, label='test_device1'))
        
      
        with self.assertRaises(HTTPRequestError):
            DeviceHandler.gen_psk(token, 'device_id', 1025)
            DeviceHandler.gen_psk(token, 'device_id', 0)
            DeviceHandler.gen_psk(token, 'device_id', 1024)

            