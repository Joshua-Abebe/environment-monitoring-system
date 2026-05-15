from publisher.sensor import Sensor
from publisher.mqtt_publisher import MQTTPublisher
from publisher.sensor_manager import SensorManager

publisher = MQTTPublisher(
    broker="localhost",
    port=1883
)

publisher.connect()

manager = SensorManager(publisher)

#temprature sensor
s1 = Sensor(
    sensor_id="s1",
    sensor_type="temprature",
    location="Lab A",
    unit="C",
    min_value=20,
    max_value=40,
    initial_value=28,
    interval=5
)

#humidity sensor
s2 = Sensor(
    sensor_id="s2",
    sensor_type="humidity",
    location="Lab A",
    unit="%",
    min_value=30,
    max_value=90,
    initial_value=60,
    interval=7
)

#air-quality sensor
s3 = Sensor(
    sensor_id="s3",
    sensor_type="humidity",
    location="Server Room",
    unit="AQI",
    min_value=10,
    max_value=150,
    initial_value=40,
    interval=10
)

manager.add_sensor(s1)
manager.add_sensor(s2)
manager.add_sensor(s3)


manager.start_all_sensors()

