import pytest
import json
import unittest
from unittest.mock import Mock, MagicMock, patch, call
from kafka import KafkaProducer

from DeviceManager.BackendHandler import KafkaHandler, KafkaInstanceHandler

class TestBackendHandler(unittest.TestCase):

    @patch("DeviceManager.BackendHandler.KafkaNotifier")
    @patch("DeviceManager.KafkaNotifier.KafkaProducer.flush")
    def test_create_event(self, kafka_instance_mock, kafka_flush):

        device = {'templates': [369], 'label': 'test_device',
                  'id': 1, 'created': '2019-08-29T18:18:07.801602+00:00'}

        KafkaHandler().create(device, meta={"service": 'admin'})
        self.assertTrue(kafka_flush.called)

    @patch("DeviceManager.BackendHandler.KafkaNotifier")
    @patch("DeviceManager.KafkaNotifier.KafkaProducer.flush")
    def test_remove_event(self, kafka_instance_mock, kafka_flush):

        device = {'templates': [369], 'label': 'test_device',
                  'id': 1, 'created': '2019-08-29T18:18:07.801602+00:00'}

        KafkaHandler().remove(device, meta={"service": 'admin'})
        self.assertTrue(kafka_flush.called)

    @patch("DeviceManager.BackendHandler.KafkaNotifier")
    @patch("DeviceManager.KafkaNotifier.KafkaProducer.flush")
    def test_update_event(self, kafka_instance_mock, kafka_flush):

        device = {'templates': [369], 'label': 'test_device',
                  'id': 1, 'created': '2019-08-29T18:18:07.801602+00:00'}

        KafkaHandler().update(device, meta={"service": 'admin'})
        self.assertTrue(kafka_flush.called)

    @patch("DeviceManager.BackendHandler.KafkaNotifier")
    @patch("DeviceManager.KafkaNotifier.KafkaProducer.flush")
    def test_configure_event(self, kafka_instance_mock, kafka_flush):

        device = {'templates': [369], 'label': 'test_device',
                  'id': 1, 'created': '2019-08-29T18:18:07.801602+00:00'}

        KafkaHandler().configure(device, meta={"service": 'admin'})
        self.assertTrue(kafka_flush.called)

    def test_verify_intance_kafka(self):
        with patch('DeviceManager.BackendHandler.KafkaHandler') as mock_kafka_instance_wrapper:
            mock_kafka_instance_wrapper.return_value = Mock()
            self.assertIsNotNone(KafkaInstanceHandler().getInstance(None))
