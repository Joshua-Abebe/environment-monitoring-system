import threading
import time
from operator import truediv

from publisher.sensor import Sensor
from publisher.mqtt_publisher import MQTTPublisher

class SensorManager:

    def __init__(self, publisher):

        self.publisher = publisher

        self.sensors = []


    def add_sensor(self, sensor):

        self.sensors.append(sensor)


    def sensor_loop(self, sensor):

        while True:
            event = sensor.create_event()

            topic = f"building/{sensor.location.lower().replace(' ', '_')}/{sensor.sensor_type}"

            self.publisher.publish_event(topic, event)

            time.sleep(sensor.interval)


    def start_all_sensors(self):

        for sensor in self.sensors:

            thread = threading.Thread(
                target=self.sensor_loop,
                args=(sensor,)
            )

            thread.daemon = True

            thread.start()

            print(f"Thread start for {sensor.sensor_id}")

        while True:
            time.sleep(1)






