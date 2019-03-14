import logging
import re
from flask import Blueprint, request, jsonify, make_response
from flask_sqlalchemy import BaseQuery
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import text, collate, func
from alembic import op

from DeviceManager.DatabaseHandler import db
from DeviceManager.DatabaseModels import handle_consistency_exception, assert_template_exists
from DeviceManager.DatabaseModels import DeviceTemplate, Device, DeviceAttr, DeviceTemplateMap
from DeviceManager.SerializationModels import import_list_schema, import_schema
from DeviceManager.SerializationModels import attr_list_schema, attr_schema
from DeviceManager.SerializationModels import parse_payload, load_attrs
from DeviceManager.SerializationModels import ValidationError
from DeviceManager.TenancyManager import init_tenant_context
from DeviceManager.KafkaNotifier import send_raw, DeviceEvent

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

    @staticmethod
    def restore_sequences():
        LOGGER.info(f"creating sequences...") 

        db.session.execute("CREATE SEQUENCE template_id START 1")
        LOGGER.info(f"template_id sequence created")

        db.session.execute("CREATE SEQUENCE attr_id START 1")
        LOGGER.info(f"attr_id sequence created")    

    @staticmethod
    def delete_records():
        LOGGER.info(f"deleting records...") 

        templates = db.session.query(DeviceTemplate)
        for template in templates:
            db.session.delete(template)
        LOGGER.info(f"deleted templates")    

        devices = db.session.query(Device)
        for device in devices:
            db.session.delete(device)
        LOGGER.info(f"deleted devices")    

    @staticmethod
    def clear_db_config():
        ImportHandler.drop_sequences()
        ImportHandler.delete_records()

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
        LOGGER.info(f"starting importing data")

        LOGGER.info(f"templates from tpl: {req.data}")
        
        init_tenant_context(req, db)
        tpl, json_payload = parse_payload(req.data[0], template_schema)
        ImportHandler.clear_db_config()

        LOGGER.info(f"templates from tpl: {req['templates']}")

        for template in json_payload['templates']:
            LOGGER.info(f"template from tpl: {template}")
            # loaded_template = DeviceTemplate(**template)
            # load_attrs(json_payload['templates']['attrs'], template, DeviceAttr, db)
            db.session.add(template)

        ImportHandler.restore_db_config()

        # loaded_template = DeviceTemplate(**tpl)
        # load_attrs(json_payload['attrs'], loaded_template, DeviceAttr, db)
        # db.session.add(loaded_template)

        try:
            db.session.commit()
            LOGGER.debug(f"Imported data into the database")
        except IntegrityError as e:
            LOGGER.error(f' {e}')
            raise HTTPRequestError(400, 'Template attribute constraints are violated by the request')
        except:
            LOGGER.error(f'roolbacking')
            db.session.rollback()    
        finally:
            db.session.close()
        # results = {
        #     'template': template_schema.dump(loaded_template),
        #     'result': 'ok'
        # }
        # return results
        return json_payload


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
        LOGGER.error(f" {error}")
        if isinstance(error.message, dict):
            return make_response(jsonify(error.message), error.error_code)
        return format_response(error.error_code, error.message)


app.register_blueprint(importing)
