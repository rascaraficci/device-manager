import json
from flask import g
from flask_alembic import Alembic
from sqlalchemy.sql import exists, select, text, column

from DeviceManager.utils import HTTPRequestError, decode_base64, get_allowed_service
from .app import app

def install_triggers(db, tenant, session=None):
    query = """
        SET search_path to {tenant};
        -- template update/creation checks

        CREATE FUNCTION validate_device_attrs() returns trigger as $$
        DECLARE
          conflict_count int;
        BEGIN
          conflict_count := (
            select count(*) from attrs as a
            left join device_template as dt on a.template_id = dt.template_id
            left join devices as d on d.id = dt.device_id
            where dt.template_id != NEW.template_id and
                  dt.device_id in (select device_id from device_template where template_id = NEW.template_id) and
                  a.label = NEW.label and a.type = NEW.type
          );
          IF (conflict_count != 0) THEN
            RAISE 'Attribute % (%) has standing conflicts', NEW.label, NEW.id using ERRCODE = 'unique_violation';
          END IF;
          RETURN NEW;
        END;
        $$ language plpgsql;

        CREATE TRIGGER validate_device_attrs_trigger BEFORE INSERT OR UPDATE ON attrs
        FOR EACH ROW EXECUTE PROCEDURE validate_device_attrs();

        -- template assignment checks

        CREATE FUNCTION validate_device() returns trigger as $$
        DECLARE
          conflict_count int;
        BEGIN
          conflict_count := (
            select count(*) from (
              select * from attrs as attr
              inner join device_template as dt on attr.template_id = dt.template_id
              where dt.device_id = NEW.device_id
            ) as curr
            inner join attrs as nattrs on curr.label = nattrs.label and curr.type = nattrs.type and nattrs.template_id = NEW.template_id
          );
          IF (conflict_count != 0) THEN
            RAISE 'Template (%) cannot be added to device (%) as it has standing attribute conflicts', NEW.template_id, NEW.device_id
            using ERRCODE = 'unique_violation';
          END IF;
          RETURN NEW;
        END;
        $$ language plpgsql;

        CREATE TRIGGER validate_device_trigger BEFORE INSERT OR UPDATE ON device_template
        FOR EACH ROW EXECUTE PROCEDURE validate_device();
    """.format(tenant=tenant)
    if session is None:
        session = db.session
    session.execute(query)
    session.commit()

def create_tenant(tenant, db):
    db.session.execute("create schema \"%s\";" % tenant)
    db.session.commit()

def switch_tenant(tenant, db, session=None):
    if session is None:
        session = db.session
    session.execute("SET search_path TO %s" % tenant)
    session.commit()

def init_tenant(tenant, db):
    query = exists(select([text("schema_name")])
                   .select_from(text("information_schema.schemata"))
                   .where(text("schema_name = '%s'" % tenant)))
    tenant_exists = db.session.query(query).scalar()
    if not tenant_exists:
        create_tenant(tenant, db)
        switch_tenant(tenant, db)

        # Makes sure alembic install its meta information tables into the db (schema/namespace)
        with app.app_context():
            g.tenant = tenant
            alembic = Alembic()
            alembic.init_app(app, run_mkdir=False)
            alembic.upgrade()

        install_triggers(db, tenant)
    else:
        switch_tenant(tenant, db)

def list_tenants(session):
    query = 'select schema_name from information_schema.schemata;'
    tenants = session.execute(query)
    result = []
    for i in tenants:
        if i.schema_name.startswith('pg'):
            continue
        if i.schema_name in ['public', 'information_schema']:
            continue

        result.append(i.schema_name)
    return result

def init_tenant_context(token, db):

    tenant = get_allowed_service(token)
    init_tenant(tenant, db)
    return tenant
