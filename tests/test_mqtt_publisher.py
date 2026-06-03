from publisher.mqtt_publisher import MQTTPublisher
from publisher.sensor import Sensor

sensor = Sensor(
    sensor_id="S1",
    sensor_type="temprature",
    location="Lab A",
    unit="C",
    min_value=20,
    max_value=40,
    initial_value=28,
    interval=5
)

publisher = MQTTPublisher(broker="localhost", port=1883)

publisher.connect()

event = sensor.create_event()

topic = "building/labA/temprature"

publisher.publish_event(topic, event)

