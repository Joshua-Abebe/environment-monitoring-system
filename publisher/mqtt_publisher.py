import json
import paho.mqtt.client as mqtt

from config.logger import logger

class MQTTPublisher:

    def __init__(self, broker, port):

        self.broker = broker
        self.port = port

        self.client = mqtt.Client()

    def connect(self):

        self.client.connect(self.broker, self.port)

        logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")

    def publish_event(self, topic, event):

        payload = json.dumps(event)

        self.client.publish(topic, payload)

        logger.info(f"\nPublished to topic: {topic} | {payload}")


        





