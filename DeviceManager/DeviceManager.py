"""
    Handles CRUD operations for devices, and their configuration on the
    FIWARE backend
"""

import json
import logging
from time import time
from flask import request
from flask import make_response
from flask import Blueprint
from utils import *
from BackendHandler import OrionHandler, KafkaHandler, PersistenceHandler
from sqlalchemy.exc import IntegrityError

from DatabaseModels import *
from SerializationModels import *
from TenancyManager import init_tenant_context

from app import app

device = Blueprint('device', __name__)

LOGGER = logging.getLogger('device-manager.' + __name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.INFO)


def serialize_full_device(orm_device):
    """
    Turn an object retrieved from database into something serializable.
    """
    data = device_schema.dump(orm_device).data
    data['attrs'] = {}
    for template in orm_device.templates:
        data['attrs'][template.id] = attr_list_schema.dump(template.attrs).data
    return data


def auto_create_template(json_payload, new_device):
    if ('attrs' in json_payload) and (new_device.templates is None):
        device_template = DeviceTemplate(label="device.%s template" % new_device.id)
        db.session.add(device_template)
        new_device.templates = [device_template]
        load_attrs(json_payload['attrs'], device_template, DeviceAttr, db)


def parse_template_list(template_list, new_device):
    new_device.templates = []
    for templateid in template_list:
        new_device.templates.append(assert_template_exists(templateid))


def generate_device_id():
    # TODO this is awful, makes me sad, but for now also makes demoing easier
    # We might want to look into an auto-configuration feature for devices, such that ids are
    # not input manually on devices
    _attempts = 0
    generated_id = ''
    while _attempts < 10 and len(generated_id) == 0:
        _attempts += 1
        new_id = create_id()
        if Device.query.filter_by(id=new_id).first() is None:
            return new_id

    raise HTTPRequestError(500, "Failed to generate unique device_id")


@device.route('/device', methods=['GET'])
def get_devices():
    """
        Fetches known devices, potentially limited by a given value.
        Ordering might be user-configurable too.
    """
    try:
        init_tenant_context(request, db)

        page_number, per_page = get_pagination(request)
        page = Device.query.paginate(page=page_number, per_page=per_page, error_out=False)
        devices = []
        for d in page.items:
            devices.append(serialize_full_device(d))

        result = json.dumps({
            'pagination': {
                'page': page.page,
                'total': page.pages,
                'has_next': page.has_next,
                'next_page': page.next_num
            },
            'devices': devices
        })
        return make_response(result, 200)
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@device.route('/device', methods=['POST'])
def create_device():
    """ Creates and configures the given device (in json) """
    try:
        tenant = init_tenant_context(request, db)
        try:
            count = int(request.args.get('count', '1'))
            clength = len(str(count))
            verbose = request.args.get('verbose', 'false') in ['true', '1', 'True']
            if verbose and count != 1:
                raise HTTPRequestError(400, "Verbose can only be used for single device creation")
        except ValueError as e:
            LOGGER.error(e)
            raise HTTPRequestError(400, "If provided, count must be integer")


        def indexed_label(base, index):
            if count == 1:
                return base
            else:
                return "{}_{:0{width}d}".format(base, index, width=clength)

        devices = []

        # Handlers
        ctx_broker_handler = OrionHandler(service=tenant)
        kafka_handler = KafkaHandler()
        subs_handler = PersistenceHandler(service=tenant)

        for i in range(0, count):
            device_data, json_payload = parse_payload(request, device_schema)
            device_data['id'] = generate_device_id()
            device_data['label'] = indexed_label(device_data['label'], i)
            # handled separately by parse_template_list
            device_data.pop('templates', None)
            orm_device = Device(**device_data)
            parse_template_list(json_payload.get('templates', []), orm_device)
            auto_create_template(json_payload, orm_device)
            db.session.add(orm_device)

            devices.append({'id': device_data['id'], 'label': device_data['label']})

            full_device = serialize_full_device(orm_device)

            # TODO remove this in favor of kafka as data broker....
            # Updating handlers

            # Generating 'device type' field for history
            type_descr = "template"
            for dev_type in full_device['attrs'].keys():
                type_descr += "_" + str(dev_type)

            ctx_broker_handler.create(full_device, type_descr)
            kafka_handler.create(full_device, meta={"service": tenant})
            
            subid = subs_handler.create(full_device['id'], type_descr)
            orm_device.persistence = subid

        try:
            db.session.commit()
        except IntegrityError as error:
            handle_consistency_exception(error)

        if verbose:
            result = json.dumps({
                'message': 'device created',
                'device': full_device
            })
        else:
            result = json.dumps({
                'message': 'devices created',
                'devices': devices
            })

        # TODO revisit iotagent notification procedure
        # protocol_handler = IotaHandler(service=tenant)
        # device_type = "virtual"
        # if orm_device.protocol != "virtual":
        #     device_type = "device"
        #     protocol_handler.create(orm_device)

        return make_response(result, 200)

    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@device.route('/device/<deviceid>', methods=['GET'])
def get_device(deviceid):
    try:
        init_tenant_context(request, db)
        orm_device = assert_device_exists(deviceid)
        return make_response(json.dumps(serialize_full_device(orm_device)), 200)
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@device.route('/device/<deviceid>', methods=['DELETE'])
def remove_device(deviceid):
    try:
        tenant = init_tenant_context(request, db)
        orm_device = assert_device_exists(deviceid)
        data = serialize_full_device(orm_device)

        subscription_handler = PersistenceHandler(service=tenant)
        subscription_handler.remove(orm_device.persistence)

        db.session.delete(orm_device)
        db.session.commit()

        results = json.dumps({'result': 'ok', 'removed_device': data})
        return make_response(results, 200)
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@device.route('/device/<deviceid>', methods=['PUT'])
def update_device(deviceid):
    try:
        device_data, json_payload = parse_payload(request, device_schema)

        # update sanity check
        if 'attrs' in json_payload:
            error = "Attributes cannot be updated inline. Update the associated template instead."
            return format_response(400, error)

        tenant = init_tenant_context(request, db)
        old_orm_device = assert_device_exists(deviceid)

        # handled separately by parse_template_list
        device_data.pop('templates')
        updated_orm_device = Device(**device_data)
        parse_template_list(json_payload.get('templates', []), updated_orm_device)
        updated_orm_device.id = deviceid

        # full_old_device = serialize_full_device(old_orm_device)
        full_device = serialize_full_device(updated_orm_device)
       

        # TODO revisit device data persistence
        subs_handler = PersistenceHandler(service=tenant)
        # TODO remove this in favor of kafka as data broker....
        ctx_broker_handler = OrionHandler(service=tenant)

        subs_handler.remove(old_orm_device.persistence)
        # Generating 'device type' field for history
        type_descr = "template"
        for dev_type in full_device['attrs'].keys():
            type_descr += "_" + str(dev_type)
        updated_orm_device.persistence = subs_handler.create(deviceid, type_descr)

        ctx_broker_handler.update(full_device, type_descr)

        kafka_handler = KafkaHandler()
        kafka_handler.update(full_device, meta={"service": tenant})

        db.session.delete(old_orm_device)
        db.session.add(updated_orm_device)

        try:
            db.session.commit()
        except IntegrityError as error:
            handle_consistency_exception(error)

        result = {'message': 'device updated', 'device': serialize_full_device(updated_orm_device)}
        return make_response(json.dumps(result))

    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


def find_attribute(orm_device, attr_name, attr_type):
    """
    Find a particular attribute in a device retrieved from database.
    Return the attribute, if found, 'None' otherwise
    """
    for template_id in orm_device['attrs']:
        for attr in orm_device['attrs'][template_id]:
            if (attr['label'] == attr_name) and (attr['type'] == attr_type):
                return attr
    return None

@device.route('/device/<deviceid>/actuate', methods=['PUT'])
def configure_device(deviceid):
    """
    Send actuation commands to the device
    """
    try:
        LOGGER.info('Received request for /device/<id>/actuate.')
        LOGGER.info('Device ID is: %s', deviceid)

        # Meta information to be published along with device actuation message
        meta = {
            'service': ''
        }
        kafka_handler = KafkaHandler()
        invalid_attrs = []
        payload = {}

        meta['service'] = init_tenant_context(request, db)

        orm_device = assert_device_exists(deviceid)
        full_device = serialize_full_device(orm_device)
        LOGGER.debug('Full device: %s', json.dumps(full_device))

        payload = json.loads(request.data)
        LOGGER.debug('Parsed request payload: %s', json.dumps(payload))

        payload['id'] = orm_device.id

        for attr in payload['attrs']:
            if find_attribute(full_device, attr, 'actuator') is None:
                invalid_attrs.append(attr)

        if not invalid_attrs:
            LOGGER.info('Sending configuration message through Kafka.')
            kafka_handler.configure(payload, meta)
            LOGGER.info('Configuration sent.')
            result = {'status': 'configuration sent to device'}
        else:
            result = {
                'status': 'some of the attributes are not configurable',
                'attrs': invalid_attrs
            }

        LOGGER.info('Configuration sent.')
        return make_response(json.dumps(result), 200)

    except HTTPRequestError as error:
        if isinstance(error.message, dict):
            return make_response(json.dumps(error.message), error.error_code)
        else:
            return format_response(error.error_code, error.message)


# Convenience template ops
@device.route('/device/<deviceid>/template/<templateid>', methods=['POST'])
def add_template_to_device(deviceid, templateid):
    """ associates given template with device """

    try:
        tenant = init_tenant_context(request, db)
        orm_device = assert_device_exists(deviceid)
        orm_template = assert_template_exists(templateid)

        orm_device.templates.append(orm_template)

        try:
            db.session.commit()
        except IntegrityError as error:
            handle_consistency_exception(error)

        result = {'message': 'device updated', 'device': serialize_full_device(orm_device)}
        return make_response(json.dumps(result))
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@device.route('/device/<deviceid>/template/<templateid>', methods=['DELETE'])
def remove_template_from_device(deviceid, templateid):
    """ removes given template from device """
    try:
        tenant = init_tenant_context(request, db)
        device = assert_device_exists(deviceid)
        relation = assert_device_relation_exists(deviceid, templateid)

        # Here (for now) there are no more validations to perform, as template removal
        # cannot violate attribute constraints

        db.session.remove(relation)
        db.session.commit()
        result = {'message': 'device updated', 'device': serialize_full_device(device)}
        return make_response(json.dumps(result))
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@device.route('/device/template/<templateid>', methods=['GET'])
def get_by_template(templateid):
    try:
        init_tenant_context(request, db)

        page_number, per_page = get_pagination(request)
        page = (
            db.session.query(Device)
            .join(DeviceTemplateMap)
            .filter_by(template_id=templateid)
            .paginate(page=page_number, per_page=per_page, error_out=False)
        )
        devices = []
        for d in page.items:
            devices.append(serialize_full_device(d))

        result = json.dumps({
            'pagination': {
                'page': page.page,
                'total': page.pages,
                'has_next': page.has_next,
                'next_page': page.next_num
            },
            'devices': devices
        })
        return make_response(result, 200)
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


app.register_blueprint(device)
