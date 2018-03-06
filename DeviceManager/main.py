from DeviceManager.app import app

# initialize modules
import DeviceManager.DeviceHandler
import DeviceManager.TemplateHandler
import DeviceManager.ErrorManager

if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)
