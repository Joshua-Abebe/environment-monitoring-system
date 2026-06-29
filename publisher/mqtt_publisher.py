import json
import paho.mqtt.client as mqtt

from config.logger import logger

class MQTTPublisher:

    def __init__(self, broker, port):

        self.broker = broker
        self.port = port

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def connect(self):

        self.client.connect(self.broker, self.port)

        # Start the network loop in a background thread so the client
        # actually services its socket. Without this, paho-mqtt never
        # sends the periodic PINGREQ keepalive, the broker drops the
        # connection after roughly 1.5x the keepalive interval, and
        # every publish() call after that silently fails on a dead
        # socket -- which is why sensors used to stop reporting after
        # ~60-90 seconds.
        self.client.loop_start()

        logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")

    def publish_event(self, topic, event):

        payload = json.dumps(event)

        self.client.publish(topic, payload)

        logger.info(f"\nPublished to topic: {topic} | {payload}")

    def disconnect(self):

        # Stop the background network thread before dropping the
        # connection so loop_start()'s thread doesn't keep spinning on
        # a closed socket after shutdown.
        self.client.loop_stop()

        self.client.disconnect()

        logger.info(f"Disconnected from MQTT broker at {self.broker}:{self.port}")
