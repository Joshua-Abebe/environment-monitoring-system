import threading
import time

from config.logger import logger

from colorama import Fore, init
init(autoreset=True)

class SensorManager:

    def __init__(self, publisher):

        self.publisher = publisher

        self.sensors = []


    def add_sensor(self, sensor):

        self.sensors.append(sensor)


    def sensor_loop(self, sensor):

        while True:
            try:
                event = sensor.create_event()

                topic = f"building/{sensor.location.lower().replace(' ', '_')}/{sensor.sensor_type}"

                self.publisher.publish_event(topic, event)

            except Exception:
                # A daemon thread that raises here would die silently --
                # the loop would just stop and that sensor would never
                # publish again, with nothing but a stderr traceback to
                # show for it. Log and keep looping instead, so one bad
                # publish (broker hiccup, etc.) can't permanently kill a
                # sensor's data.
                logger.exception(f"{Fore.RED}Sensor {sensor.sensor_id} failed to publish, will retry{Fore.RESET}")

            time.sleep(sensor.interval)


    def start_all_sensors(self):

        for sensor in self.sensors:

            thread = threading.Thread(
                target=self.sensor_loop,
                args=(sensor,)
            )

            thread.daemon = True

            thread.start()

            logger.info(f"Thread start for {sensor.sensor_id}")

        while True:
            time.sleep(1)
