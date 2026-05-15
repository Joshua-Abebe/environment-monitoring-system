import json
import paho.mqtt.client as mqtt

class MQTTSubscriber:

    def __init__(self, broker, port):

        self.broker = broker
        self.port = port

        self.client = mqtt.Client()

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message


    def on_connect(self, client, userdata, flags, rc):

        print(f"Connected to MQTT broker at {self.broker}:{self.port}")

        self.client.subscribe("building/#")

        print("Subscribed to topic building/#")


    def on_message(self, client, userdata, msg):

        payload = msg.payload.decode()

        event = json.loads(payload)

        print("\nRecieved event:")
        print(f"Topic: {msg.topic}")

        print(event)


    def start(self):

        self.client.connect(self.broker, self.port)

        self.client.loop_forever()



if __name__ == "__main__":
    subscriber = MQTTSubscriber(broker="localhost", port=1883)
    subscriber.start()



