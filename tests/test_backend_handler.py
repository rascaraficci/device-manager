import pytest
import json
import unittest
from unittest.mock import Mock, MagicMock, patch, call

from DeviceManager.BackendHandler import KafkaHandler


class TestBackendHandler(unittest.TestCase):

    @patch("DeviceManager.BackendHandler.KafkaNotifier")
    def test_create_event(self, kafka_instance_mock):

        device = {'templates': [369], 'label': 'test_device',
                  'id': 1, 'created': '2019-08-29T18:18:07.801602+00:00'}

        KafkaHandler().create(device, meta={"service": 'admin'})

    @patch("DeviceManager.BackendHandler.KafkaNotifier")
    def test_remove_event(self, kafka_instance_mock):

        device = {'templates': [369], 'label': 'test_device',
                  'id': 1, 'created': '2019-08-29T18:18:07.801602+00:00'}

        KafkaHandler().remove(device, meta={"service": 'admin'})

    @patch("DeviceManager.BackendHandler.KafkaNotifier")
    def test_update_event(self, kafka_instance_mock):

        device = {'templates': [369], 'label': 'test_device',
                  'id': 1, 'created': '2019-08-29T18:18:07.801602+00:00'}

        KafkaHandler().update(device, meta={"service": 'admin'})

    @patch("DeviceManager.BackendHandler.KafkaNotifier")
    def test_configure_event(self, kafka_instance_mock):

        device = {'templates': [369], 'label': 'test_device',
                  'id': 1, 'created': '2019-08-29T18:18:07.801602+00:00'}

        KafkaHandler().configure(device, meta={"service": 'admin'})
