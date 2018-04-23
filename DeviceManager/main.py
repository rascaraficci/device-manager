from flask import g
from flask_migrate import Migrate

from DeviceManager.app import app

# initialize modules
import DeviceManager.DeviceHandler
import DeviceManager.TemplateHandler
import DeviceManager.ErrorManager

from .DatabaseHandler import db
from .StatusMonitor import StatusMonitor
from .TenancyManager import list_tenants

with app.app_context():
    g.tenant = '__status_monitor__'
    for tenant in list_tenants(db.session):
        StatusMonitor(tenant)

migrate = Migrate(app, db)

if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)
