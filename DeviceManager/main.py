from flask_migrate import Migrate

from DeviceManager.app import app

# initialize modules
import DeviceManager.DeviceHandler
import DeviceManager.TemplateHandler
import DeviceManager.ErrorManager

from .DatabaseModels import db
from .StatusMonitor import StatusMonitor
from .TenancyManager import list_tenants

for tenant in list_tenants(db.session):
    StatusMonitor(tenant)

migrate = Migrate(app, db)

if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)
