import time
import json
from kafka import KafkaConsumer, KafkaProducer
from kafka import ConsumerRebalanceListener
from kafka.errors import KafkaTimeoutError

import redis

from .conf import CONFIG
from .KafkaNotifier import get_topic
from .DatabaseModels import db, Device

import threading

class Listener(ConsumerRebalanceListener):
    def __init__(self, monitor):
        self.__monitor = monitor
        self.__collectors = {}

    def on_partitions_assigned(self, assigned):
        # print('got listener event {} {}'.format(len(assigned), assigned))
        for partition in assigned:
            self.__monitor.collect(partition.partition)
            if partition not in self.__collectors.keys():
                # print('will start iterator')
                self.__monitor.begin(partition.partition)

class StatusMonitor:
    def __init__(self, tenant):
        self.producer = KafkaProducer(value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                                      bootstrap_servers=CONFIG.get_kafka_url())

        self.tenant = tenant
        self.topic=get_topic(self.tenant, CONFIG.device_subject)

        self.redis = redis.StrictRedis(host=CONFIG.redis_host, port=CONFIG.redis_port)

        self.__consumer_thread = threading.Thread(target=self.run)
        self.__consumer_thread.daemon = True
        self.__consumer_thread.start()

    @staticmethod
    def wait_init(consumer):
        done = False
        while not done:
            try:
                # make sure we process initial partition assignment messages
                consumer.poll()
                consumer.seek_to_end()
                done = True
            except AssertionError as error:
                # give kafka some time to assign us a partition
                time.sleep(1)

    def run(self):
        group_id="device-manager.monitor"
        start = time.time()
        # print('will create consumer {} {} {}'.format(CONFIG.get_kafka_url(), group_id, self.topic))
        consumer = KafkaConsumer(bootstrap_servers=CONFIG.get_kafka_url(), group_id=group_id)
        consumer.subscribe(topics=[self.topic], listener=Listener(self))
        StatusMonitor.wait_init(consumer)
        # print('kafka consumer created {} - {}'.format(self.topic, time.time() - start))
        # print(consumer.assignment())
        for message in consumer:
            # print("Got kafka event [{}] {}".format(self.topic, message))
            data = None
            try:
                data = json.loads(message.value)
            except Exception as error:
                print("Received message is not valid json {}".format(error))
                continue

            metadata = data.get('metadata', None)
            if metadata is None:
                print('Invalid kafka event detected - no metadata included')
                continue

            reason = metadata.get('reason', None)
            if reason == 'statusUpdate':
                continue

            deviceid = metadata.get('deviceid', None)
            tenant = metadata.get('tenant', None)
            if (deviceid is None) or (tenant is None):
                print('Missing device identification from event')
                continue

            self.set_online(tenant, deviceid, message.partition, metadata.get('exp', None))

    @staticmethod
    def get_key_for(tenant, device, partition):
        return 'st:{}:{}:{}:exp'.format(tenant, device, partition)

    @staticmethod
    def parse_key_from(key):
        parsed = key.split(':')
        return {
            'tenant': parsed[1],
            'device': parsed[2],
            'partiion': parsed[3]
        }

    def notify(self, tenant, device, status):
        message = {
            'metadata': {
                'deviceid': device,
                'tenant': tenant,
                'status': status,
                'reason': 'statusUpdate'
            }
        }
        self.producer.send(self.topic, message)

    @staticmethod
    def default_exp(tenant, device):
        db.session.execute("SET search_path TO %s" % tenant)
        device = db.session.query(Device).filter(Device.id == device).one()
        for template in device.templates:
            for attr in template.config_attrs:
                if (attr.type == "meta") and (attr.label == "device_timeout"):
                    return int(attr.static_value)/1000.0
        return CONFIG.status_timeout


    def set_online(self, tenant, device, partition, exp):
        """
        Brands given device as online for the stipulated period of time 'exp'
        """
        if exp is None:
            exp = StatusMonitor.default_exp(tenant, device)

        print('will set {}:{} online for {}s'.format(tenant, device, exp))

        key = StatusMonitor.get_key_for(tenant, device, partition)
        old_ts = self.redis.get(key)
        if old_ts is None:
            # publish online event
            self.notify(tenant, device, 'online')

        self.redis.set(key, time.time() + exp)

    def begin(self, partition):
        gc_thread = threading.Thread(target=self.iterate, args=(partition, -1))
        gc_thread.daemon = True
        gc_thread.start()

    def iterate(self, partition=None, times=-1):
        """
        Periodically invoke iterator
        """
        # print('starting iterator')
        while times != 0:
            # now = time.time()
            # print('[times] gc is about to run {}'.format(now - self.lastgc))
            # self.lastgc = now
            self.collect(partition)
            time.sleep(2)
            if times > 0:
                times -= 1

    def collect(self, partition):
        match = StatusMonitor.get_key_for(self.tenant, '*', partition)
        devices = []

        cursor, data = self.redis.scan(0, match, count=1000)
        for i in data:
            if i is not None:
                devices.append(i.decode('utf-8'))
        # print('scan {} {} {}'.format(match, cursor, data))
        while cursor != 0:
            cursor, data = self.redis.scan(cursor, match, count=1000)
            for i in data:
                if i is not None:
                    devices.append(i.decode('utf-8'))
            # print('scan {} {}'.format(cursor, data))

        # print('gc devices {}'.format(devices))
        now = time.time()
        for device in devices:
            exp = float(self.redis.get(device).decode('utf-8'))
            # print('will check {} {}'.format(device, exp))
            if now > exp:
                self.redis.delete(device)
                print('device {} offline'.format(device))
                parsed = device.split(':')
                self.notify(parsed[1],parsed[2],'offline')

    @staticmethod
    def get_status(tenant, device=None):
        """
        Returns boolean indicating whether device is online or not.
        """
        client = redis.StrictRedis(host=CONFIG.redis_host, port=CONFIG.redis_port)
        match = StatusMonitor.get_key_for(tenant, device if device is not None else '*', '*')
        status = {}
        timeref = time.time()

        def iterate(data):
            for key in data:
                if key is not None:
                    device = StatusMonitor.parse_key_from(key.decode('utf-8'))['device']
                    exp = float(client.get(key).decode('utf-8'))
                    if (exp is not None) and (timeref < exp):
                        status[device] = 'online'
                    else:
                        status[device] = 'offline'

        cursor, data = client.scan(0, match, count=1000)
        iterate(data)
        while cursor != 0:
            cursor, data = client.scan(cursor, match, count=1000)
            iterate(data)

        return status


