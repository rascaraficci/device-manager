import pytest

from DeviceManager.LoggerHandler import LoggerHandler
from DeviceManager.utils import HTTPRequestError

import unittest
from unittest.mock import Mock, MagicMock, patch

class TestLoggerHandler(unittest.TestCase):

    def test_update_valid_level_log(self):
        self.assertTrue(LoggerHandler.update_log_level("info"), "")
        with self.assertRaises(HTTPRequestError):   
            LoggerHandler.update_log_level("teste")

    def test_get_actual_level_log(self):
        level = LoggerHandler.get_log_level()
        self.assertIsNotNone(level)
        