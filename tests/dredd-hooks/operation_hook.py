from __future__ import absolute_import
import dredd_hooks as hooks
import json

# This shouldn't be needed
from werkzeug.datastructures import MultiDict

from DeviceManager.DeviceHandler import DeviceHandler
from DeviceManager.TemplateHandler import TemplateHandler
from token_generator import generate_token


class Request:
    def __init__(self, data):
        self.headers = data['headers']
        self.args = data['args']
        self.data = data['body']


template_id = 0
device_id = ""


def sort_attributes(device, attribute):
    device[attribute] = sorted(device[attribute], key=lambda k: k['label'])


def create_sample_template():
    global template_id
    template = {
        "label": "SensorModel",
        "attrs": [
            {
                "label": "temperature",
                "type": "dynamic",
                "value_type": "float"
            },
            {
                "label": "model-id",
                "type": "static",
                "value_type": "string",
                "static_value": "model-001"
            },
            {
                "label": "shared_key",
                "type": "static",
                "value_type": "psk"
            }
        ]
    }
    req = {
        'headers': {
            'authorization': generate_token(),
            'Content-Type': 'application/json'
        },
        'args': {},
        'body': json.dumps(template)
    }

    result = TemplateHandler.create_template(Request(req))
    template_id = result['template']['id']


@hooks.before('Templates > Templates > Get the current list of templates')
@hooks.before('Templates > Template info > Get template info')
@hooks.before('Templates > Template info > Update template info')
@hooks.before('Templates > Template info > Delete template')
def register_new_template(transaction):
    global template_id
    create_sample_template()


@hooks.before('Devices > Device info > Update device info')
@hooks.before('Devices > Devices > Register a new device')
def register_new_device(transaction):
    global template_id
    create_sample_template()
    device_json = json.loads(transaction['request']['body'])
    device_json['templates'] = [template_id]
    transaction['request']['body'] = json.dumps(device_json)


@hooks.before('Devices > Device info > Get the current list of devices > Example 2')
@hooks.before('Internal > Device > Get the current list of devices > Example 2')
def update_onlyids_query(transaction):
    transaction['request']['uri'] = transaction['request']['uri'].replace('idsOnly=false',
                                                                          'idsOnly=true')
    transaction['fullPath'] = transaction['fullPath'].replace('idsOnly=false', 'idsOnly=true')


@hooks.before('Devices > Device info > Get the current list of devices > Example 1')
@hooks.before('Devices > Device info > Get the current list of devices associated with given template')
def create_single_device(transaction):
    global template_id, device_id
    create_sample_template()
    device = {
        "label": "test_device",
        "templates": [template_id]
    }
    req = {
        'headers': {
            'authorization': generate_token(),
            'Content-Type': 'application/json'
        },
        'args': {
            'count': 1,
            'verbose': False
        },
        'body': json.dumps(device)
    }
    result = DeviceHandler.create_device(Request(req))
    device_id = result['devices'][0]['id']
    
@hooks.before('Internal > Device > Get the current list of devices > Example 1')
def create_single_device_and_gen_psk(transaction):
    global device_id
    create_single_device(transaction)
    DeviceHandler.gen_psk(generate_token(), device_id, 16, None)

@hooks.before('Devices > Device info > Get device info')
@hooks.before('Devices > Device info > Update device info')
@hooks.before('Devices > Device info > Configure device')
@hooks.before('Devices > Device info > Delete device')
@hooks.before('Devices > Device info > Generate PSK')
def create_device_and_update_device_id(transaction):
    global device_id
    create_single_device(transaction)
    transaction['fullPath'] = transaction['fullPath'].replace('efac', device_id)
    
@hooks.before('Internal > Device > Get device info')
def prepare_env_psk(transaction):
    global device_id    
    create_device_and_update_device_id(transaction)
    DeviceHandler.gen_psk(generate_token(), device_id, 16, None)
    
    
@hooks.before_validation('Devices > Device info > Get device info')
@hooks.before_validation('Internal > Device > Get device info')
def update_expected_ids_single_device(transaction):
    global template_id, device_id
    expected_body = json.loads(transaction['expected']['body'])
    str_template_id = "{}".format(template_id)
    expected_body["attrs"][str_template_id] = expected_body["attrs"].pop("4865")
    for attr in expected_body["attrs"][str_template_id]:
        attr['template_id'] = str_template_id
    expected_body["templates"] = [str_template_id]
    expected_body["id"] = device_id
    transaction['expected']['body'] = json.dumps(expected_body)


@hooks.before_validation('Devices > Device info > Update device info')
def update_expected_ids_single_device_update(transaction):
    global template_id, device_id
    expected_body = json.loads(transaction['expected']['body'])
    str_template_id = "{}".format(template_id)
    expected_body["device"]["attrs"][str_template_id] = expected_body["device"]["attrs"].pop("4865")
    for attr in expected_body["device"]["attrs"][str_template_id]:
        attr['template_id'] = str_template_id
    expected_body["device"]["templates"] = [str_template_id]
    expected_body["device"]["id"] = device_id
    transaction['expected']['body'] = json.dumps(expected_body)


@hooks.before('Devices > Device info > Delete device')
def update_expected_ids_single_device_delete(transaction):
    global template_id, device_id
    expected_body = json.loads(transaction['expected']['body'])
    str_template_id = "{}".format(template_id)
    expected_body["removed_device"]["attrs"][str_template_id] = expected_body["removed_device"]["attrs"].pop("4865")
    for attr in expected_body["removed_device"]["attrs"][str_template_id]:
        attr['template_id'] = str_template_id
    expected_body["removed_device"]["templates"] = [str_template_id]
    expected_body["removed_device"]["id"] = device_id
    transaction['expected']['body'] = json.dumps(expected_body)


@hooks.before('Devices > Device info > Get the current list of devices associated with given template')
@hooks.before('Devices > Device info > Get the current list of devices > Example 1')
@hooks.before('Internal > Device > Get the current list of devices > Example 1')
def update_expected_ids_multiple_devices(transaction):
    global template_id, device_id
    expected_body = json.loads(transaction['expected']['body'])
    str_template_id = "{}".format(template_id)
    expected_body["devices"][0]["attrs"][str_template_id] = expected_body["devices"][0]["attrs"].pop("4865")
    for attr in expected_body["devices"][0]["attrs"][str_template_id]:
        attr['template_id'] = str_template_id
    expected_body["devices"][0]["templates"] = [str_template_id]
    expected_body["devices"][0]["id"] = device_id
    transaction['expected']['body'] = json.dumps(expected_body)


@hooks.before('Devices > Device info > Get the current list of devices associated with given template')
@hooks.before('Templates > Template info > Get template info')
@hooks.before('Templates > Template info > Update template info')
@hooks.before('Templates > Template info > Delete template')
def update_template_id(transaction):
    global template_id
    transaction['fullPath'] = transaction['fullPath'].replace('4865', '{}'.format(template_id))


@hooks.after_each
def clean_scenario(transaction):
    # This shouldn't be needed - controller class shouln't expose flask dependent params
    # TODO remove
    args = MultiDict([
        ('page_size', 10),
        ('page_num', 1),
        ('attr_format', 'both')
    ])
    req = {
        'headers': {
            'authorization': generate_token()
        },
        'args': args,
        'body': ''
    }

    result = DeviceHandler.get_devices(Request(req))
    for device in result['devices']:
        DeviceHandler.delete_device(Request(req), device['id'])

    result = TemplateHandler.get_templates(Request(req))
    for template in result['templates']:
        # print(template)
        TemplateHandler.remove_template(Request(req), template['id'])


@hooks.before_validation('Templates > Templates > Get the current list of templates')
def order_attributes(transaction):
    template = json.loads(transaction['expected']['body'])
    sort_attributes(template['templates'][0], 'data_attrs')
    sort_attributes(template['templates'][0], 'attrs')
    transaction['expected']['body'] = json.dumps(template)

    template = json.loads(transaction['real']['body'])
    sort_attributes(template['templates'][0], 'data_attrs')
    sort_attributes(template['templates'][0], 'attrs')
    transaction['real']['body'] = json.dumps(template)
