import logging
import re
from flask import Blueprint, request, jsonify, make_response
from flask_sqlalchemy import BaseQuery
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import text, collate, func
from alembic import op

from DeviceManager.utils import *
from DeviceManager.utils import create_id, get_pagination, format_response
from DeviceManager.utils import HTTPRequestError
from DeviceManager.conf import CONFIG
from DeviceManager.BackendHandler import OrionHandler, KafkaHandler, PersistenceHandler

from DeviceManager.DatabaseHandler import db
from DeviceManager.DatabaseModels import handle_consistency_exception, assert_template_exists
from DeviceManager.DatabaseModels import DeviceTemplate, Device, DeviceAttr, DeviceOverride, DeviceTemplateMap
from DeviceManager.SerializationModels import import_list_schema, import_schema, device_schema, device_list_schema, template_schema, template_list_schema
from DeviceManager.SerializationModels import attr_list_schema, attr_schema
from DeviceManager.SerializationModels import parse_payload, load_attrs
from DeviceManager.SerializationModels import ValidationError
from DeviceManager.TenancyManager import init_tenant_context
from DeviceManager.KafkaNotifier import send_raw, DeviceEvent
from DeviceManager.DeviceHandler import auto_create_template, parse_template_list, serialize_full_device

from DeviceManager.app import app
from DeviceManager.utils import format_response, HTTPRequestError, get_pagination

from DeviceManager.Logger import Log
from datetime import datetime
import time
import json

importing = Blueprint('import', __name__)

LOGGER = Log().color_log()

def attr_format(req, result):
    """ formats output attr list acording to user input """
    attrs_format = req.args.get('attr_format', 'both')

    def remove(d,k):
        try:
            LOGGER.info(f' will remove {k}')
            d.pop(k)
        except KeyError:
            pass

    if attrs_format == 'split':
        remove(result, 'attrs')
    elif attrs_format == 'single':
        remove(result, 'config_attrs')
        remove(result, 'data_attrs')

    return result


class ImportHandler:

    def __init__(self):
        pass

    @staticmethod
    def drop_sequences():
        LOGGER.info(f"dropping sequences...") 

        db.session.execute("DROP SEQUENCE template_id")
        LOGGER.info(f"template_id sequence dropped")

        db.session.execute("DROP SEQUENCE attr_id")
        LOGGER.info(f"attr_id sequence dropped")

        # db.session.execute("DROP SEQUENCE override_id")
        # LOGGER.info(f"override_id sequence dropped")

    @staticmethod
    def restore_sequences():
        LOGGER.info(f"creating sequences...") 

        max_template_id = db.session.query(func.max(DeviceTemplate.id)).scalar() + 1
        db.session.execute("CREATE SEQUENCE template_id START {}".format(str(max_template_id)))
        LOGGER.info(f"template_id sequence created")

        max_attr_id = db.session.query(func.max(DeviceAttr.id)).scalar() + 1
        db.session.execute("CREATE SEQUENCE attr_id START {}".format(str(max_attr_id)))
        LOGGER.info(f"attr_id sequence created")    

    @staticmethod
    def delete_records():
        LOGGER.info(f"deleting records...") 

        overrides = db.session.query(DeviceOverride)
        for override in overrides:
            db.session.delete(override)
        LOGGER.info(f"deleted overrides")

        devices = db.session.query(Device)
        for device in devices:
            db.session.delete(device)
        LOGGER.info(f"deleted devices") 

        templates = db.session.query(DeviceTemplate)
        for template in templates:
            db.session.delete(template)
        LOGGER.info(f"deleted templates")    

    @staticmethod
    def clear_db_config():
        ImportHandler.drop_sequences()
        ImportHandler.delete_records()
        db.session.flush()

    @staticmethod
    def restore_db_config():
        ImportHandler.restore_sequences()

    @staticmethod
    def import_data(req):
        """
        Creates a new import.

        :param req: The received HTTP request, as created by Flask.
        :return The created template.
        :raises HTTPRequestError: If no authorization token was provided (no
        tenant was informed)
        :raises HTTPRequestError: If template attribute constraints were
        violated. This might happen if two attributes have the same name, for
        instance.
        """
        LOGGER.info(f"starting importing data...")
        
        init_tenant_context(req, db)
        tpl, json_payload = parse_payload(req, import_schema)

        ImportHandler.clear_db_config()

        saved_templates = []
        for template in tpl['templates']:
            loaded_template = DeviceTemplate(**template)
            for json in json_payload['templates']:
                if(json['id'] == template["id"]):
                    load_attrs(json['attrs'], loaded_template, DeviceAttr, db)
            db.session.add(loaded_template)
            saved_templates.append(loaded_template)


        # Handlers
        kafka_handler = KafkaHandler()
        if CONFIG.orion:
            ctx_broker_handler = OrionHandler(service=tenant)
            subs_handler = PersistenceHandler(service=tenant)
        else:
            ctx_broker_handler = None
            subs_handler = None

        full_device = None
        orm_devices = []

        saved_devices = []
        for device in tpl['devices']:
            device.pop('templates', None)
            loaded_device = Device(**device)
            for json in json_payload['devices']:
                if(json['id'] == device["id"]):
                    loaded_device.templates = []

                    for template_id in json.get('templates', []):
                        for saved_template in saved_templates:
                            if(template_id == saved_template.id):
                                loaded_device.templates.append(saved_template)

                    auto_create_template(json, loaded_device)
            db.session.add(loaded_device)
            saved_devices.append(loaded_device)

        ImportHandler.restore_db_config()


        try:
            db.session.commit()

            # devices = []
            # for orm_device in saved_devices:
            #     devices.append(
            #         {
            #             'id': orm_device.id,
            #             'label': orm_device.label
            #         }
            #     )

            #     full_device = serialize_full_device(orm_device, tenant)

                # # Updating handlers
                # kafka_handler.create(full_device, meta={"service": tenant})
                # if CONFIG.orion:
                #     # Generating 'device type' field for history
                #     type_descr = "template"
                #     for dev_type in full_device['attrs'].keys():
                #         type_descr += "_" + str(dev_type)
                #     # TODO remove this in favor of kafka as data broker....
                #     ctx_broker_handler.create(full_device, type_descr)
                #     sub_id = subs_handler.create(full_device['id'], type_descr)
                #     orm_device.persistence = sub_id

            LOGGER.info(f"Imported data into the database")

        except IntegrityError as e:
            LOGGER.error(f' {e}')
            raise HTTPRequestError(400, 'Template attribute constraints are violated by the request')
        except:
            LOGGER.error(f'roolbacking')
            db.session.rollback()    
        finally:
            db.session.close()


        results = {
            'message': 'data imported'
        }
        return results


@importing.route('/import', methods=['POST'])
def flask_import_data():
    try:
        result = ImportHandler.import_data(request)

        LOGGER.info(f"Importing data")

        return make_response(jsonify(result), 200)

    except ValidationError as e:
        results = {'message': 'failed to parse attr', 'errors': e}
        LOGGER.error(f" {e}")
        return make_response(jsonify(results), 400)
    except HTTPRequestError as error:
        LOGGER.error(f" {error.message}")
        return jsonify({"error": "Error"})
        # if isinstance(error.message, dict):
        #     return make_response(jsonify(error.message), error.error_code)
        # return format_response(error.error_code, error.message)


app.register_blueprint(importing)
