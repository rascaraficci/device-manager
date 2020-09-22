import unittest

from DeviceManager.app import app


class TestApp(unittest.TestCase):

    def test_should_use_JSONIFY_PRETTYPRINT_REGULAR_property_off(self):
        self.assertFalse(app.config['JSONIFY_PRETTYPRINT_REGULAR'])
