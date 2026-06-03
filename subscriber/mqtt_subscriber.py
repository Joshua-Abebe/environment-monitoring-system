import json
import paho.mqtt.client as mqtt

from colorama import Fore, init
init(autoreset=True)

from config.settings import MYSQL_CONFIG
from config.settings import MQTT_CONFIG
from config.settings import MONGO_URI
from config.logger import logger
from database.mysql_handler import MySQLHandler
from database.mongodb_handler import MongoDBHandler


class MQTTSubscriber:

    def __init__(self, broker, port):

        self.broker = broker
        self.port = port

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        #connect to MySQL DB
        self.mysql_handler = MySQLHandler(
            **MYSQL_CONFIG
        )
        #connect to MongoDB
        self.mongodb_handler = MongoDBHandler(MONGO_URI)


    def on_connect(self, client, userdata, flags, reasonCode, properties):

        logger.info(f"{Fore.GREEN}Connected to MQTT broker at {self.broker}:{self.port}{Fore.RESET}")

        self.client.subscribe("building/#")

        logger.info(f"{Fore.YELLOW}Subscribed to topic building/#{Fore.RESET}")


    def validate_event(self, event):

        required_fields = [
            "sensor_id",
            "sensor_type",
            "location",
            "unit",
            "value",
            "timestamp"
        ]

        for field in required_fields:

            if field not in event:
                return False
        return True


    def on_message(self, client, userdata, msg):

        payload = msg.payload.decode()

        event = json.loads(payload)

        logger.info(f"Recieved event: {event} | Topic: {msg.topic}")


        if not self.validate_event(event):

            logger.warning(f"{Fore.RED}Received invalid event, missing required fields{Fore.RESET}")
            logger.error(f"Invalid event: {event}")

            return

        self.mysql_handler.insert_readings(
            sensor_id=event["sensor_id"],
            value=event["value"],
            timestamp=event["timestamp"]
        )

        logger.info(f"{Fore.GREEN}Inserted into MySQL{Fore.RESET}")

        #Alert logic
        sensor_type = event["sensor_type"]
        value = event["value"]

        if sensor_type == "temperature" and value > 35:

            logger.warning(Fore.RED + "TEMPERATURE ALERT" + Fore.RESET)

            self.mysql_handler.insert_alert(
                sensor_id=event["sensor_id"],
                severity="HIGH",
                message="HIGH Temperature Detected",
                timestamp=event["timestamp"]
            )
        elif sensor_type == "humidity" and value > 70:

            logger.warning(Fore.RED + "HUMIDITY ALERT" + Fore.RESET)

            self.mysql_handler.insert_alert(
                sensor_id=event["sensor_id"],
                severity="MEDIUM",
                message="HIGH Humidity Detected",
                timestamp=event["timestamp"]
            )
        elif sensor_type == "air_quality" and value > 80:

            logger.warning(Fore.RED + "AIR QUALITY ALERT" + Fore.RESET)

            self.mysql_handler.insert_alert(
                sensor_id=event["sensor_id"],
                severity="HIGH",
                message="POOR Air Quality Detected",
                timestamp=event["timestamp"]
            )

            #Insert raw event to MongoDB
        self.mongodb_handler.insert_event(event)



    def start(self):

        self.client.connect(self.broker, self.port)

        self.client.loop_forever()



if __name__ == "__main__":
    subscriber = MQTTSubscriber(
        **MQTT_CONFIG
    )
    try:
        subscriber.start()

    except KeyboardInterrupt:

        print(f"{Fore.YELLOW}Subscriber shutting down......{Fore.RESET}")