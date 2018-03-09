"""
    Handles CRUD operations for devices, and their configuration on the
    FIWARE backend
"""

import logging
import re
from flask import request
from flask import Blueprint
from sqlalchemy.exc import IntegrityError

from DeviceManager.utils import *
from DeviceManager.conf import CONFIG
from DeviceManager.BackendHandler import OrionHandler, KafkaHandler, PersistenceHandler

from DeviceManager.DatabaseModels import db, assert_device_exists, assert_template_exists
from DeviceManager.DatabaseModels import handle_consistency_exception, assert_device_relation_exists
from DeviceManager.DatabaseModels import DeviceTemplate, DeviceAttr, Device, DeviceTemplateMap
from DeviceManager.SerializationModels import *
from DeviceManager.TenancyManager import init_tenant_context
from DeviceManager.app import app


device = Blueprint('device', __name__)

LOGGER = logging.getLogger('device-manager.' + __name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.INFO)


def serialize_full_device(orm_device):
    data = device_schema.dump(orm_device).data
    data['attrs'] = {}
    for template in orm_device.templates:
        data['attrs'][template.id] = attr_list_schema.dump(template.attrs).data
    return data


def auto_create_template(json_payload, new_device):
    if ('attrs' in json_payload) and (new_device.templates is None):
        device_template = DeviceTemplate(
            label="device.%s template" % new_device.id)
        db.session.add(device_template)
        new_device.templates = [device_template]
        load_attrs(json_payload['attrs'], device_template, DeviceAttr, db)


def parse_template_list(template_list, new_device):
    new_device.templates = []
    for template_id in template_list:
        new_device.templates.append(
            assert_template_exists(template_id, db.session))


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


class DeviceHandler(object):

    def __init__(self):
        pass

    @staticmethod
    def indexed_label(count, c_length, base, index):
        if count == 1:
            return base
        else:
            return "{}_{:0{width}d}".format(base, index, width=c_length)

    @staticmethod
    def generate_device_id():
        """
        Creates a new device id
        :return The new ID
        :rtype int
        :raises HTTPRequestError: If this function can't generate a new valid
        ID after 10 attempts.
        """

        # TODO this is awful, makes me sad, but for now also makes demoing
        # easier We might want to look into an auto-configuration feature for
        # devices, such that ids are not input manually on devices

        _attempts = 0
        generated_id = ''
        while _attempts < 10 and len(generated_id) == 0:
            _attempts += 1
            new_id = create_id()
            if Device.query.filter_by(id=new_id).first() is None:
                return new_id

        raise HTTPRequestError(500, "Failed to generate unique device_id")

    @staticmethod
    def list_ids(req):
        """
        Fetches the list of known device ids.
        :rtype JSON
        :raises HTTPRequestError: If no authorization token was provided (no
        tenant was informed)
        """

        init_tenant_context(req, db)

        data = []
        for id in db.session.query(Device.id).all():
            data.append(id[0])
        return data

    @staticmethod
    def get_devices(req):
        """
        Fetches known devices, potentially limited by a given value. Ordering
        might be user-configurable too.

        :param req: The received HTTP request, as created by Flask.
        :return A JSON containing pagination information and the device list
        :rtype JSON
        :raises HTTPRequestError: If no authorization token was provided (no
        tenant was informed)
        """

        if req.args.get('idsOnly', 'false').lower() in ['true', '1', '']:
            return DeviceHandler.list_ids(req)

        init_tenant_context(req, db)

        page_number, per_page = get_pagination(req)
        pagination = {'page': page_number, 'per_page': per_page, 'error_out': False}

        parsed_query = []
        query = req.args.getlist('attr')
        for attr in query:
            parsed = re.search('^(.+){1}=(.+){1}$', attr)
            parsed_query.append("attrs.label = '{}'".format(parsed.group(1)))
            parsed_query.append("attrs.static_value = '{}'".format(parsed.group(2)))

        target_label = req.args.get('label', None)
        if target_label:
            parsed_query.append("devices.label = '{}'".format(target_label))

        if len(parsed_query):
            page = db.session.query(Device) \
                             .join(DeviceTemplateMap) \
                             .join(DeviceTemplate) \
                             .join(DeviceAttr) \
                             .filter(*parsed_query) \
                             .paginate(**pagination)
        else:
            page = db.session.query(Device).paginate(**pagination)


        devices = []
        for d in page.items:
            devices.append(serialize_full_device(d))

        result = {
            'pagination': {
                'page': page.page,
                'total': page.pages,
                'has_next': page.has_next,
                'next_page': page.next_num
            },
            'devices': devices
        }
        return result

    @staticmethod
    def get_device(req, device_id):
        """
        Fetches a single device.

        :param req: The received HTTP request, as created by Flask.
        :param device_id: The requested device.
        :return A Device
        :rtype Device, as described in DatabaseModels package
        :raises HTTPRequestError: If no authorization token was provided (no
        tenant was informed)
        :raises HTTPRequestError: If this device could not be found in
        database.
        """

        init_tenant_context(req, db)
        orm_device = assert_device_exists(device_id)
        return serialize_full_device(orm_device)

    @staticmethod
    def create_device(req):
        """
        Creates and configures the given device.

        :param req: The received HTTP request, as created by Flask.
        :return The created device or a list of device summary. This depends on
        which value the verbose (/?verbose=true) has - if true, only one device
        can be created ("count" argument can't be used or - at least - it must
        be exactly "1") and the full device is returned. If false, "count" can
        be used with higher values and only the devices summary (a structure
        containing all device IDs and their labels) is returned.
        :raises HTTPRequestError: If no authorization token was provided (no
        tenant was informed)
        :raises HTTPRequestError: If verbose is used with multiple device
        creation request.
        :raises HTTPRequestError: If count argument ("?count=X") is provided
        and it is not an integer.

        """

        tenant = init_tenant_context(req, db)
        try:
            count = int(req.args.get('count', '1'))
        except ValueError as e:
            LOGGER.error(e)
            raise HTTPRequestError(400, "If provided, count must be integer")

        c_length = len(str(count))
        verbose = req.args.get('verbose', 'false') in ['true', '1', 'True']
        if verbose and count != 1:
            raise HTTPRequestError(
                400, "Verbose can only be used for single device creation")

        devices = []

        # Handlers
        kafka_handler = KafkaHandler()
        if CONFIG.orion:
            ctx_broker_handler = OrionHandler(service=tenant)
            subs_handler = PersistenceHandler(service=tenant)
        else:
            ctx_broker_handler = None
            subs_handler = None

        full_device = None

        for i in range(0, count):
            device_data, json_payload = parse_payload(req, device_schema)
            device_data['id'] = DeviceHandler.generate_device_id()
            device_data['label'] = DeviceHandler.indexed_label(count, c_length, device_data['label'], i)
            # handled separately by parse_template_list
            device_data.pop('templates', None)
            orm_device = Device(**device_data)
            parse_template_list(json_payload.get('templates', []), orm_device)
            auto_create_template(json_payload, orm_device)
            db.session.add(orm_device)

            devices.append(
                {
                    'id': device_data['id'],
                    'label': device_data['label']
                }
            )

            full_device = serialize_full_device(orm_device)

            # Updating handlers
            kafka_handler.create(full_device, meta={"service": tenant})
            if CONFIG.orion:
                # Generating 'device type' field for history
                type_descr = "template"
                for dev_type in full_device['attrs'].keys():
                    type_descr += "_" + str(dev_type)
                # TODO remove this in favor of kafka as data broker....
                ctx_broker_handler.create(full_device, type_descr)
                sub_id = subs_handler.create(full_device['id'], type_descr)
                orm_device.persistence = sub_id

        try:
            db.session.commit()
        except IntegrityError as error:
            handle_consistency_exception(error)

        if verbose:
            result = {
                'message': 'device created',
                'device': full_device
            }
        else:
            result = {
                'message': 'devices created',
                'devices': devices
            }
        return result

    @staticmethod
    def delete_device(req, device_id):
        """
        Deletes a single device.

        :param req: The received HTTP request, as created by Flask.
        :param device_id: The device to be removed.
        :return The removed device.
        :rtype JSON
        :raises HTTPRequestError: If no authorization token was provided (no
        tenant was informed)
        :raises HTTPRequestError: If this device could not be found in
        database.
        """

        tenant = init_tenant_context(req, db)
        orm_device = assert_device_exists(device_id)
        data = serialize_full_device(orm_device)

        kafka_handler = KafkaHandler()
        kafka_handler.remove(data, meta={"service": tenant})
        if CONFIG.orion:
            subscription_handler = PersistenceHandler(service=tenant)
            subscription_handler.remove(orm_device.persistence)

        db.session.delete(orm_device)
        db.session.commit()

        results = {'result': 'ok', 'removed_device': data}
        return results

    @staticmethod
    def update_device(req, device_id):
        """
        Updated the information about a particular device

        :param req: The received HTTP request, as created by Flask.
        :param device_id: The device to be updated.
        :return The updated device.
        :rtype JSON
        :raises HTTPRequestError: If no authorization token was provided (no
        tenant was informed)
        :raises HTTPRequestError: If this device could not be found in
        database.
        """
        device_data, json_payload = parse_payload(req, device_schema)

        # update sanity check
        if 'attrs' in json_payload:
            LOGGER.warn('Got request with "attrs" field set. Ignoring.')
            json_payload.pop('attrs')

        tenant = init_tenant_context(req, db)
        old_orm_device = assert_device_exists(device_id)

        # handled separately by parse_template_list
        device_data.pop('templates')
        updated_orm_device = Device(**device_data)
        parse_template_list(json_payload.get(
            'templates', []), updated_orm_device)
        updated_orm_device.id = device_id

        full_device = serialize_full_device(updated_orm_device)

        if CONFIG.orion:
            # Create subscription pointing to history service
            # (STH, logstash based persister)
            subs_handler = PersistenceHandler(service=tenant)
            subs_handler.remove(old_orm_device.persistence)
            # Generating 'device type' field for subscription request
            type_descr = "template"
            for dev_type in full_device['attrs'].keys():
                type_descr += "_" + str(dev_type)
            updated_orm_device.persistence = subs_handler.create(
                device_id, type_descr)

            ctx_broker_handler = OrionHandler(service=tenant)
            ctx_broker_handler.update(serialize_full_device(old_orm_device), type_descr)

        kafka_handler = KafkaHandler()
        kafka_handler.update(full_device, meta={"service": tenant})

        db.session.delete(old_orm_device)
        db.session.add(updated_orm_device)

        try:
            db.session.commit()
        except IntegrityError as error:
            handle_consistency_exception(error)

        result = {
            'message': 'device updated',
            'device': serialize_full_device(updated_orm_device)
        }
        return result

    @staticmethod
    def configure_device(req, device_id):
        """
        Send actuation commands to the device

        :param req: The received HTTP request, as created by Flask.
        :param device_id: The device which should receive the actuation message
        :return A status on whether the message was sent to the device or not.
        Note that this is not a guarantee that the device actually performed
        what was requested.
        :rtype JSON
        """
        # Meta information to be published along with device actuation message
        meta = {
            'service': ''
        }
        kafka_handler = KafkaHandler()
        invalid_attrs = []

        meta['service'] = init_tenant_context(req, db)

        orm_device = assert_device_exists(device_id)
        full_device = serialize_full_device(orm_device)
        LOGGER.debug('Full device: %s', json.dumps(full_device))

        payload = json.loads(req.data)
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
        return result

    @staticmethod
    def add_template_to_device(req, device_id, template_id):
        """
        Associates given template with device

        :param req: The received HTTP request, as created by Flask.
        :param device_id: The device which should be updated
        :param template_id: The template to be added to this device.
        :raises HTTPRequestError: If no authorization token was provided (no
        tenant was informed)
        :raises HTTPRequestError: If this device or template could not be found
        in database.
        :return A status on whether the device was updated, and the new
        structure for that device.
        :rtype JSON
        """
        init_tenant_context(req, db)
        orm_device = assert_device_exists(device_id)
        orm_template = assert_template_exists(template_id)

        orm_device.templates.append(orm_template)

        try:
            db.session.commit()
        except IntegrityError as error:
            handle_consistency_exception(error)

        result = {
            'message': 'device updated',
            'device': serialize_full_device(orm_device)
        }

        return result

    @staticmethod
    def remove_template_from_device(req, device_id, template_id):
        """
        Disassociates given template with device

        :param req: The received HTTP request, as created by Flask.
        :param device_id: The device which should be updated
        :param template_id: The template to be removed from this device.
        :raises HTTPRequestError: If no authorization token was provided (no
        tenant was informed)
        :raises HTTPRequestError: If this device or template could not be found
        in database.
        :return A status on whether the device was updated, and the new
        structure for that device.
        :rtype JSON
        """
        init_tenant_context(req, db)
        updated_device = assert_device_exists(device_id)
        relation = assert_device_relation_exists(device_id, template_id)

        # Here (for now) there are no more validations to perform, as template
        # removal cannot violate attribute constraints

        db.session.remove(relation)
        db.session.commit()
        result = {
            'message': 'device updated',
            'device': serialize_full_device(updated_device)
        }

        return result

    @staticmethod
    def get_by_template(req, template_id):
        """
        Return a list of devices that have a particular template associated to
        it

        :param req: The received HTTP request, as created by Flask.
        :param template_id: The template to be considered
        :raises HTTPRequestError: If no authorization token was provided (no
        tenant was informed)
        :raises HTTPRequestError: If this device or template could not be found
        in database.
        :return A list of devices that are associated to the selected template.
        :rtype JSON
        """
        init_tenant_context(req, db)

        page_number, per_page = get_pagination(req)
        page = (
            db.session.query(Device)
            .join(DeviceTemplateMap)
            .filter_by(template_id=template_id)
            .paginate(page=page_number, per_page=per_page, error_out=False)
        )
        devices = []
        for d in page.items:
            devices.append(serialize_full_device(d))

        result = {
            'pagination': {
                'page': page.page,
                'total': page.pages,
                'has_next': page.has_next,
                'next_page': page.next_num
            },
            'devices': devices
        }
        return result


@device.route('/device', methods=['GET'])
def flask_get_devices():
    """
    Fetches known devices, potentially limited by a given value. Ordering might
    be user-configurable too.

    Check API description for more information about request parameters and
    headers.
    """
    try:
        result = DeviceHandler.get_devices(request)
        resp = make_response(json.dumps(result), 200)
        resp.mimetype = "application/json"
        return resp
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            resp = make_response(json.dumps(e.message), e.error_code)
            resp.mimetype = "application/json"
            return resp
        else:
            return format_response(e.error_code, e.message)


@device.route('/device', methods=['POST'])
def flask_create_device():
    """
    Creates and configures the given device (in json).

    Check API description for more information about request parameters and
    headers.
    """
    try:
        result = DeviceHandler.create_device(request)
        resp = make_response(json.dumps(result), 200)
        resp.mimetype = "application/json"
        return resp
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@device.route('/device/<device_id>', methods=['GET'])
def flask_get_device(device_id):
    try:
        result = DeviceHandler.get_device(request, device_id)
        resp = make_response(json.dumps(result), 200)
        resp.mimetype = "application/json"
        return resp
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@device.route('/device/<device_id>', methods=['DELETE'])
def flask_remove_device(device_id):
    try:
        results = DeviceHandler.delete_device(request, device_id)
        resp = make_response(json.dumps(results), 200)
        resp.mimetype = "application/json"
        return resp
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@device.route('/device/<device_id>', methods=['PUT'])
def flask_update_device(device_id):
    try:
        results = DeviceHandler.update_device(request, device_id)
        resp = make_response(json.dumps(results), 200)
        resp.mimetype = "application/json"
        return resp
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@device.route('/device/<device_id>/actuate', methods=['PUT'])
def flask_configure_device(device_id):
    """
    Send actuation commands to the device
    """
    try:
        result = DeviceHandler.configure_device(request, device_id)
        resp = make_response(json.dumps(result), 200)
        resp.mimetype = "application/json"
        return resp

    except HTTPRequestError as error:
        if isinstance(error.message, dict):
            return make_response(json.dumps(error.message), error.error_code)
        else:
            return format_response(error.error_code, error.message)


# Convenience template ops
@device.route('/device/<device_id>/template/<template_id>', methods=['POST'])
def flask_add_template_to_device(device_id, template_id):
    try:
        result = DeviceHandler.add_template_to_device(
            request, device_id, template_id)
        resp = make_response(json.dumps(result), 200)
        resp.mimetype = "application/json"
        return resp
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@device.route('/device/<device_id>/template/<template_id>', methods=['DELETE'])
def flask_remove_template_from_device(device_id, template_id):
    try:
        result = DeviceHandler.remove_template_from_device(
            request, device_id, template_id)
        resp = make_response(json.dumps(result), 200)
        resp.mimetype = "application/json"
        return resp
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@device.route('/device/template/<template_id>', methods=['GET'])
def flask_get_by_template(template_id):
    try:
        result = DeviceHandler.get_by_template(request, template_id)
        resp = make_response(json.dumps(result), 200)
        resp.mimetype = "application/json"
        return resp
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(json.dumps(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


app.register_blueprint(device)
