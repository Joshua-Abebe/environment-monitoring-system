import json
import paho.mqtt.client as mqtt

from database.mysql_handler import MySQLHandler
from database.mongodb_handler import MongoDBHandler

class MQTTSubscriber:

    def __init__(self, broker, port):

        self.broker = broker
        self.port = port

        self.client = mqtt.Client()

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        #connect to MySQL DB
        self.mysql_handler = MySQLHandler(
            host="localhost",
            user="abc",
            password="projects5555",
            database="environment_monitoring"
        )
        #connect to MongoDB
        self.mongodb_handler = MongoDBHandler(
            uri="mongodb://localhost:27017"
        )


    def on_connect(self, client, userdata, flags, rc):

        print(f"Connected to MQTT broker at {self.broker}:{self.port}")

        self.client.subscribe("building/#")

        print("Subscribed to topic building/#")


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

        print("\nRecieved event:")
        print(f"Topic: {msg.topic}")

        print(event)

        if not self.validate_event(event):

            print("Received invalid event, missing required fields")

            return

        self.mysql_handler.insert_readings(
            sensor_id=event["sensor_id"],
            value=event["value"],
            timestamp=event["timestamp"]
        )

        print("Inserted into MySQL")

        #Alert logic
        sensor_type = event["sensor_type"]
        value = event["value"]

        if sensor_type == "temperature" and value > 35:

            print("TEMPERATURE ALERT")

            self.mysql_handler.insert_alert(
                sensor_id=event["sensor_id"],
                severity="HIGH",
                message="HIGH Temprature Detected",
                timestamp=event["timestamp"]
            )
        elif sensor_type == "humidity" and value > 70:

            print("HUMIDITY ALERT")

            self.mysql_handler.insert_alert(
                sensor_id=event["sensor_id"],
                severity="MEDIUM",
                message="HIGH Humidity Detected",
                timestamp=event["timestamp"]
            )
        elif sensor_type == "air_quality" and value > 80:

            print("AIR QUALITY ALERT")

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
    subscriber = MQTTSubscriber(broker="localhost", port=1883)
    subscriber.start()



