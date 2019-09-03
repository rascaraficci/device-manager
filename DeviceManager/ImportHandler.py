import logging
import re
import copy
import json
from flask import Blueprint, request, jsonify, make_response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func

from DeviceManager.app import app
from DeviceManager.Logger import Log
from DeviceManager.utils import format_response, HTTPRequestError
from DeviceManager.conf import CONFIG
from DeviceManager.BackendHandler import KafkaHandler

from DeviceManager.DatabaseHandler import db
from DeviceManager.DatabaseModels import DeviceTemplate, Device, DeviceAttr, DeviceOverride
from DeviceManager.SerializationModels import import_schema
from DeviceManager.SerializationModels import parse_payload, load_attrs
from DeviceManager.SerializationModels import ValidationError
from DeviceManager.TenancyManager import init_tenant_context
from DeviceManager.DeviceHandler import auto_create_template, serialize_full_device

importing = Blueprint('import', __name__)

LOGGER = Log().color_log()

class ImportHandler:

    kafka_handler = None

    def __init__(self):
        pass

    @classmethod
    def verifyInstance(cls, kafka):
        """
        Instantiates a connection with Kafka, was created because 
        previously the connection was being created in KafkaNotifier
        once time every import.
        
        :param kafka: An instance of KafkaHandler.
        :return An instance of KafkaHandler used to notify
        """

        if kafka is None:
            cls.kafka_handler = KafkaHandler()

        return cls.kafka_handler

    def drop_sequences():
        db.session.execute("DROP SEQUENCE template_id")
        db.session.execute("DROP SEQUENCE attr_id")
        LOGGER.info(f" Removed sequences") 


    def replace_ids_by_import_ids(my_json):
        new_json = json.loads(my_json)
        return json.dumps(new_json).replace('\"id\":', '\"import_id\":')


    def restore_template_sequence():
        max_template_id = 1
        current_max_template_id = db.session.query(func.max(DeviceTemplate.id)).scalar()
        if current_max_template_id is not None:
            max_template_id = current_max_template_id + 1
        db.session.execute("CREATE SEQUENCE template_id START {}".format(str(max_template_id)))

    def restore_attr_sequence():
        max_attr_id = 1
        current_max_attr_id = db.session.query(func.max(DeviceAttr.id)).scalar()
        if current_max_attr_id is not None:
            max_attr_id = current_max_attr_id + 1
        db.session.execute("CREATE SEQUENCE attr_id START {}".format(str(max_attr_id)))

    def restore_sequences():
        ImportHandler.restore_template_sequence()
        ImportHandler.restore_attr_sequence()
        LOGGER.info(f" Restored sequences") 

    def notifies_deletion_to_kafka(cls, device, tenant):
        data = serialize_full_device(device, tenant)
        kafka_handler_instance = cls.verifyInstance(cls.kafka_handler)
        kafka_handler_instance.remove(data, meta={"service": tenant})

    def delete_records(tenant):
        overrides = db.session.query(DeviceOverride)
        for override in overrides:
            db.session.delete(override)
        LOGGER.info(f" Deleted overrides")

        devices = db.session.query(Device)
        for device in devices:
            db.session.delete(device)
            ImportHandler.notifies_deletion_to_kafka(device, tenant)
        LOGGER.info(f" Deleted devices") 

        templates = db.session.query(DeviceTemplate)
        for template in templates:
            db.session.delete(template)
        LOGGER.info(f" Deleted templates")    


    def clear_db_config(tenant):
        ImportHandler.drop_sequences()
        ImportHandler.delete_records(tenant)
        db.session.flush()


    def restore_db_config():
        ImportHandler.restore_sequences()


    def save_templates(json_data, json_payload):
        saved_templates = []
        for template in json_data['templates']:
            loaded_template = DeviceTemplate(**template)
            for json in json_payload['templates']:
                if(json['import_id'] == template["id"]):
                    load_attrs(json['attrs'], loaded_template, DeviceAttr, db)
            db.session.add(loaded_template)
            saved_templates.append(loaded_template) 

        LOGGER.info(f" Saved templates")     
        return saved_templates    


    def set_templates_on_device(loaded_device, json, saved_templates):
        loaded_device.templates = []
        for template_id in json.get('templates', []):
            for saved_template in saved_templates:
                if(template_id == saved_template.id):
                    loaded_device.templates.append(saved_template) 

        auto_create_template(json, loaded_device)


    def save_devices(json_data, json_payload, saved_templates):
        saved_devices = []
        for device in json_data['devices']:
            device.pop('templates', None)
            loaded_device = Device(**device)
            for json in json_payload['devices']:
                if(json['id'] == device["id"]):
                    ImportHandler.set_templates_on_device(loaded_device, json, saved_templates)

            db.session.add(loaded_device)
            saved_devices.append(loaded_device) 

        LOGGER.info(f" Saved devices")        
        return saved_devices    


    def notifies_creation_to_kafka(saved_devices, tenant):
        kafka_handler = KafkaHandler()
        for orm_device in saved_devices:
            full_device = serialize_full_device(orm_device, tenant)
            kafka_handler.create(full_device, meta={"service": tenant})


    @staticmethod
    def import_data(req):
        """
        Import data.

        :param req: The received HTTP request, as created by Flask.
        :return The status message.
        :raises HTTPRequestError: If no authorization token was provided (no
        tenant was informed)
        :raises HTTPRequestError: If import attribute constraints were
        violated. This might happen if two attributes have the same name, for
        instance.
        """

        saved_templates = []
        saved_devices = []

        try:
            tenant = init_tenant_context(req, db)

            ImportHandler.clear_db_config(tenant)
            
            original_req_data = copy.copy(req.data)

            original_payload = json.loads(original_req_data)

            req.data = ImportHandler.replace_ids_by_import_ids(req.data)

            json_data, json_payload = parse_payload(req, import_schema)

            saved_templates = ImportHandler.save_templates(json_data, json_payload)

            saved_devices = ImportHandler.save_devices(json_data, original_payload, saved_templates)

            ImportHandler.restore_db_config()

            ImportHandler.notifies_creation_to_kafka(saved_devices, tenant)

            db.session.commit()

        except IntegrityError as e:
            LOGGER.error(f' {e}')
            db.session.rollback()
            raise HTTPRequestError(400, 'Template attribute constraints are violated by the request')
        except Exception as e:
            LOGGER.error(f' {e}')
            db.session.rollback()
            raise HTTPRequestError(400, 'Failed to import data')    
        finally:
            db.session.close()

        results = {
            'message': 'data imported!'
        }
        return results


@importing.route('/import', methods=['POST'])
def flask_import_data():
    try:
        LOGGER.info(f" Starting importing data...")

        result = ImportHandler.import_data(request)

        LOGGER.info(f" Imported data!")

        return make_response(jsonify(result), 201)

    except ValidationError as e:
        results = {'message': 'failed to parse attr', 'errors': e}
        LOGGER.error(f" {e}")
        return make_response(jsonify(results), 400)
    except HTTPRequestError as error:
        LOGGER.error(f" {error.message}")
        if isinstance(error.message, dict):
            return make_response(jsonify(error.message), error.error_code)
        return format_response(error.error_code, error.message)


app.register_blueprint(importing)
