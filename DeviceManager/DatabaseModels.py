from datetime import datetime
import re
import sqlalchemy
from flask_sqlalchemy import SQLAlchemy

from DeviceManager.app import app
from DeviceManager.utils import HTTPRequestError
from DeviceManager.conf import CONFIG

app.config['SQLALCHEMY_DATABASE_URI'] = CONFIG.get_db_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class DeviceOverride(db.Model):
    __tablename__ = 'overrides'

    id = db.Column(db.Integer, db.Sequence('override_id'), primary_key=True)

    did = db.Column(db.String(8), db.ForeignKey('devices.id'))
    aid = db.Column(db.Integer, db.ForeignKey('attrs.id'))

    device = db.relationship('Device', back_populates='overrides')
    attr = db.relationship('DeviceAttr', back_populates='overrides')

    static_value = db.Column(db.String(128))

class DeviceAttr(db.Model):
    __tablename__ = 'attrs'

    id = db.Column(db.Integer, db.Sequence('attr_id'), primary_key=True)
    label = db.Column(db.String(128), nullable=False)
    created = db.Column(db.DateTime, default=datetime.now)
    updated = db.Column(db.DateTime, onupdate=datetime.now)

    type = db.Column(db.String(32), nullable=False)
    value_type = db.Column(db.String(32), nullable=False)
    static_value = db.Column(db.String(128))

    template_id = db.Column(db.Integer, db.ForeignKey('templates.id'))
    template = db.relationship("DeviceTemplate", back_populates="attrs")

    parent_id = db.Column(db.Integer, db.ForeignKey('attrs.id'))
    parent = db.relationship("DeviceAttr", remote_side=[id], back_populates="children")
    children = db.relationship("DeviceAttr", back_populates="parent", cascade="delete")

    # remove known overrides if this attribute is removed
    overrides = db.relationship('DeviceOverride', cascade="delete")

    # Any given template must not possess two attributes with the same type, label
    __table_args__ = (
        sqlalchemy.UniqueConstraint('template_id', 'type', 'label'),
        sqlalchemy.CheckConstraint("((template_id IS NULL) AND NOT (parent_id IS NULL)) OR \
                                     (NOT (template_id IS NULL) AND (parent_id IS NULL))")
    )

    def __repr__(self):
        return "<Attr(label='{}', type='{}', value_type='{}', children='{}', parent={})>".format(
            self.label, self.type, self.value_type, self.children, self.parent)


class DeviceTemplate(db.Model):
    __tablename__ = 'templates'

    id = db.Column(db.Integer, db.Sequence('template_id'), primary_key=True)
    label = db.Column(db.String(128), nullable=False)
    created = db.Column(db.DateTime, default=datetime.now)
    updated = db.Column(db.DateTime, onupdate=datetime.now)

    attrs = db.relationship("DeviceAttr", back_populates="template", lazy='joined', cascade="delete")
    devices = db.relationship("Device", secondary='device_template',
                              back_populates="templates", passive_deletes='all')

    config_attrs = db.relationship('DeviceAttr',
                             primaryjoin=db.and_(DeviceAttr.template_id == id,
                                                 DeviceAttr.type != 'static',
                                                 DeviceAttr.type != 'dynamic'))
    data_attrs = db.relationship('DeviceAttr',
                                 primaryjoin=db.and_(DeviceAttr.template_id == id,
                                                     DeviceAttr.type.in_(('static', 'dynamic'))))

    def __repr__(self):
        return "<Template(label={}, attrs={})>".format(self.label, self.attrs)


class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.String(8), unique=True, nullable=False, primary_key=True)
    label = db.Column(db.String(128), nullable=False)
    created = db.Column(db.DateTime, default=datetime.now)
    updated = db.Column(db.DateTime, onupdate=datetime.now)

    # template_id = db.Column(db.Integer, db.ForeignKey('templates.id'), nullable=False)
    templates = db.relationship("DeviceTemplate", secondary='device_template', back_populates="devices")
    overrides = db.relationship("DeviceOverride", back_populates="device", cascade="delete")

    persistence = db.Column(db.String(128))

    def __repr__(self):
        return "<Device(label='%s')>" % self.label


class DeviceTemplateMap(db.Model):
    __tablename__ = 'device_template'
    device_id = db.Column(db.String(8), db.ForeignKey('devices.id'),
                          primary_key=True, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey('templates.id'),
                            primary_key=True, index=True, nullable=False)


def assert_device_exists(device_id, session=None):
    """
    Assert that a device exists, returning the object retrieved from the
    database.
    """
    try:
        if session:
            with session.no_autoflush:
                return session.query(Device).filter_by(id=device_id).one()
        else:
            return Device.query.filter_by(id=device_id).one()
    except sqlalchemy.orm.exc.NoResultFound:
        raise HTTPRequestError(404, "No such device: %s" % device_id)


def assert_template_exists(template_id, session=None):
    try:
        if session:
            with session.no_autoflush:
                return session.query(DeviceTemplate).filter_by(id=template_id).one()
        else:
            return DeviceTemplate.query.filter_by(id=template_id).one()
    except sqlalchemy.orm.exc.NoResultFound:
        raise HTTPRequestError(404, "No such template: %s" % template_id)


def assert_device_relation_exists(device_id, template_id):
    try:
        return DeviceTemplateMap.query.filter_by(device_id=device_id, template_id=template_id).one()
    except sqlalchemy.orm.exc.NoResultFound:
        raise HTTPRequestError(404, "Device %s is not associated with template %s" % (device_id, template_id))


def handle_consistency_exception(error):
    raise HTTPRequestError(400, error.orig.diag.message_primary)
