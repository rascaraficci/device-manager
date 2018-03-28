# object to json sweetness
import json
from marshmallow import Schema, fields, post_dump, ValidationError

from DeviceManager.utils import HTTPRequestError
from DeviceManager.DatabaseModels import DeviceAttr

class MetaSchema(Schema):
    id = fields.Int()
    label = fields.Str(required=True)
    created = fields.DateTime(dump_only=True)
    updated = fields.DateTime(dump_only=True)
    type = fields.Str(required=True)
    value_type = fields.Str(required=True)
    static_value = fields.Field()

class AttrSchema(Schema):
    id = fields.Int()
    label = fields.Str(required=True)
    created = fields.DateTime(dump_only=True)
    updated = fields.DateTime(dump_only=True)
    type = fields.Str(required=True)
    value_type = fields.Str(required=True)
    static_value = fields.Field()
    template_id = fields.Str(dump_only=True)

    metadata = fields.Nested(MetaSchema, many=True, attribute='children')

    @post_dump
    def remove_null_values(self, data):
        return {
            key: value for key, value in data.items() \
            if (value is not None) and ((isinstance(value, list) and len(value)) or not isinstance(value, list))
        }

attr_schema = AttrSchema()
attr_list_schema = AttrSchema(many=True)

class TemplateSchema(Schema):
    id = fields.Int()
    label = fields.Str(required=True)
    created = fields.DateTime(dump_only=True)
    updated = fields.DateTime(dump_only=True)
    attrs = fields.Nested(AttrSchema, many=True, dump_only=True)
    data_attrs = fields.Nested(AttrSchema, many=True, dump_only=True)
    config_attrs = fields.Nested(AttrSchema, many=True, dump_only=True)

    @post_dump
    def remove_null_values(self, data):
        return {key: value for key, value in data.items() if value is not None}

template_schema = TemplateSchema()
template_list_schema = TemplateSchema(many=True)

class DeviceSchema(Schema):
    id = fields.String(dump_only=True)
    label = fields.Str(required=True)
    created = fields.DateTime(dump_only=True)
    updated = fields.DateTime(dump_only=True)
    templates = fields.Nested(TemplateSchema, only=('id'), many=True)
    # protocol = fields.Str(required=True)
    # frequency = fields.Int()
    # topic = fields.Str(load_only=True)

    @post_dump
    def remove_null_values(self, data):
        return {key: value for key, value in data.items() if value is not None}

device_schema = DeviceSchema()
device_list_schema = DeviceSchema(many=True)

def parse_payload(request, schema):
    try:
        content_type = request.headers.get('Content-Type')
        if (content_type is None) or (content_type != "application/json"):
            raise HTTPRequestError(400, "Payload must be valid JSON, and Content-Type set accordingly")
        json_payload = json.loads(request.data)
        data = schema.load(json_payload).data
    except ValueError:
        raise HTTPRequestError(400, "Payload must be valid JSON, and Content-Type set accordingly")
    except ValidationError as errors:
        results = {'message': 'failed to parse input', 'errors': errors}
        raise HTTPRequestError(400, results)
    return data, json_payload

def load_attrs(attr_list, parent_template, base_type, db):
    """

    :rtype:
    """
    for attr in attr_list:
        try:
            entity = attr_schema.load(attr).data
            try:
                children = entity.pop('children')
            except KeyError:
                children = []

            orm_entity = base_type(template=parent_template, **entity)
            db.session.add(orm_entity)

            for child in children:
                orm_child = DeviceAttr(parent=orm_entity, **child)
                db.session.add(orm_child)
        except ValidationError as errors:
            results = {'message': 'failed to parse attr', 'errors': errors}
            raise HTTPRequestError(400, results)
