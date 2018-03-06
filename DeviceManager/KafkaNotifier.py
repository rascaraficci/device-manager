import base64
import logging
import json

import requests
from kafka import KafkaProducer
from kafka.errors import KafkaTimeoutError

from DeviceManager.conf import CONFIG

LOGGER = logging.getLogger('device-manager.' + __name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)


class DeviceEvent:
    CREATE = "create"
    UPDATE = "update"
    REMOVE = "remove"
    CONFIGURE = "configure"


class NotificationMessage:
    event = ""
    data = None
    meta = None

    def __init__(self, ev, d, m):
        self.event = ev
        self.data = d
        self.meta = m

    def to_json(self):
        return {"event": self.event, "data": self.data, "meta": self.meta}


kafka_address = CONFIG.kafka_host + ':' + CONFIG.kafka_port
kf_prod = KafkaProducer(value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                        bootstrap_servers=kafka_address)

# Maps services to their managed topics
topic_map = {}

def get_topic(service, subject):
    if service in topic_map.keys():
        return topic_map[service]

    target = "{}/topic/{}".format(CONFIG.data_broker, subject)
    userinfo = {
        "username": "device-manager",
        "service": service
    }

    jwt = "{}.{}.{}".format(base64.b64encode("model".encode()).decode(),
                            base64.b64encode(json.dumps(userinfo).encode()).decode(),
                            base64.b64encode("signature".encode()).decode())

    response = requests.get(target, headers={"authorization": jwt})
    if 200 <= response.status_code < 300:
        payload = response.json()
        topic_map[service] = payload['topic']
        return payload['topic']
    return None


def send_notification(event, device, meta):
    # TODO What if Kafka is not yet up?

    full_msg = NotificationMessage(event, device, meta)
    try:
        topic = get_topic(meta['service'], CONFIG.subject)
        if topic is None:
            LOGGER.error("Failed to retrieve named topic to publish to")

        kf_prod.send(topic, full_msg.to_json())
        kf_prod.flush()
    except KafkaTimeoutError:
        LOGGER.error("Kafka timed out.")
