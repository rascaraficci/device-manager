""" Service configuration module """

import os


class Config(object):
    """ Abstracts configuration, either retrieved from environment or from ctor arguments """
    def __init__(self,
                 db="dojot_devm",
                 dbhost="postgres",
                 dbuser="postgres",
                 dbpass=None,
                 dbdriver="postgresql+psycopg2",
                 kafka_host="kafka",
                 kafka_port="9092",
                 broker="http://data-broker",
                 subject="dojot.device-manager.device",
                 device_subject="device-data",
                 redis_host="device-manager-redis",
                 redis_port="6379",
                 create_db=True):
        # Postgres configuration data
        self.dbname = os.environ.get('DBNAME', db)
        self.dbhost = os.environ.get('DBHOST', dbhost)
        self.dbuser = os.environ.get('DBUSER', dbuser)
        self.dbpass = os.environ.get('DBPASS', dbpass)
        self.dbdriver = os.environ.get('DBDRIVER', dbdriver)
        self.create_db = os.environ.get('CREATE_DB', create_db)
        # Kafka configuration
        self.kafka_host = os.environ.get('KAFKA_HOST', kafka_host)
        self.kafka_port = os.environ.get('KAFKA_PORT', kafka_port)

        self.orion = os.environ.get('ORION', 'false') in ['True', 'true', 'TRUE', '1']

        # Data broker configuration
        # Full baseurl of data-broker
        self.data_broker = os.environ.get('BROKER', broker)
        # Which subject to publish new device information to
        self.subject = os.environ.get('SUBJECT', subject)
        self.device_subject = os.environ.get('DEVICE_SUBJECT', device_subject)

        self.redis_host = os.environ.get('REDIS_HOST', redis_host)
        self.redis_port = int(os.environ.get('REDIS_PORT', redis_port))

    def get_db_url(self):
        """ From the config, return a valid postgresql url """
        if self.dbpass is not None:
            return "{}://{}:{}@{}/{}".format(self.dbdriver, self.dbuser, self.dbpass,
                                             self.dbhost, self.dbname)
        else:
            return "{}://{}@{}/{}".format(self.dbdriver, self.dbuser, self.dbhost, self.dbname)

    def get_kafka_url(self):
        return "{}:{}".format(self.kafka_host, self.kafka_port)


CONFIG = Config()
