import pytest
import json
import unittest
from unittest.mock import Mock, MagicMock, patch, call

from alchemy_mock.mocking import AlchemyMagicMock

from DeviceManager.ImportHandler import ImportHandler


class TestImportHandler(unittest.TestCase):

    @patch('DeviceManager.ImportHandler.db')
    def test_drop_sequence(self, db_mock):
        db_mock.session = AlchemyMagicMock()
        self.assertIsNone(ImportHandler.drop_sequences())

    def test_replaceIds_to_imoprtIds(self):
        json_import = '{"id": "test_value"}'

        result = ImportHandler.replace_ids_by_import_ids(json_import)
        self.assertIsNotNone(result)
        self.assertIn('import_id', result)

    @patch('DeviceManager.ImportHandler.db')
    def test_restore_template_sequence(self, db_mock):
        db_mock.session = AlchemyMagicMock()
        self.assertIsNone(ImportHandler.restore_template_sequence())

    @patch('DeviceManager.ImportHandler.db')
    def test_restore_attr_sequence(self, db_mock):
        db_mock.session = AlchemyMagicMock()
        self.assertIsNone(ImportHandler.restore_attr_sequence())

    @patch('DeviceManager.ImportHandler.db')
    def test_restore_sequences(self, db_mock):
        db_mock.session = AlchemyMagicMock()
        self.assertIsNone(ImportHandler.restore_sequences())

    def test_notifies_deletion_to_kafka(self):
        with patch('DeviceManager.ImportHandler.serialize_full_device') as mock_serialize_device_wrapper:
            mock_serialize_device_wrapper.return_value = {'templates': [369], 'label': 'test_device', 'id': 1,
                                                          'created': '2019-08-29T18:18:07.801602+00:00'}

            with patch.object(ImportHandler, "verifyInstance", return_value=MagicMock()):
                ImportHandler().notifies_deletion_to_kafka('test_device', 'admin')

    @patch('DeviceManager.ImportHandler.db')
    def test_delete_records(self, db_mock):
        db_mock.session = AlchemyMagicMock()
        self.assertIsNone(ImportHandler.delete_records('admin'))

    @patch('DeviceManager.ImportHandler.db')
    def test_clear_db_config(self, db_mock):
        db_mock.session = AlchemyMagicMock()
        self.assertIsNone(ImportHandler.clear_db_config('admin'))

    @patch('DeviceManager.ImportHandler.db')
    def test_restore_db_config(self, db_mock):
        db_mock.session = AlchemyMagicMock()
        self.assertIsNone(ImportHandler.restore_db_config())

