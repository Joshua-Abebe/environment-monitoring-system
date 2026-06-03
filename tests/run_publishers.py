from publisher.sensor import Sensor
from publisher.mqtt_publisher import MQTTPublisher
from publisher.sensor_manager import SensorManager

from colorama import Fore, init
init(autoreset=True)

publisher = MQTTPublisher(
    broker="localhost",
    port=1883
)

publisher.connect()

manager = SensorManager(publisher)

#temprature sensor
s1 = Sensor(
    sensor_id="s1",
    sensor_type="temperature",
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
    sensor_type="air_quality",
    location="Server Room",
    unit="AQI",
    min_value=10,
    max_value=150,
    initial_value=40,
    interval=10
)

s4 = Sensor(
    sensor_id="s4",
    sensor_type="temperature",
    location="Lab B",
    unit="C",
    min_value=20,
    max_value=40,
    initial_value=27,
    interval=5
)

s5 = Sensor(
    sensor_id="s5",
    sensor_type="humidity",
    location="Lab B",
    unit="%",
    min_value=30,
    max_value=90,
    initial_value=70,
    interval=7
)


s6 = Sensor(
    sensor_id="s6",
    sensor_type="air quality",
    location="Office 1",
    unit="AQI",
    min_value=10,
    max_value=150,
    initial_value=45,
    interval=9
)

manager.add_sensor(s1)
manager.add_sensor(s2)
manager.add_sensor(s3)
manager.add_sensor(s4)
manager.add_sensor(s5)
manager.add_sensor(s6)


try:
    manager.start_all_sensors()

except KeyboardInterrupt:
    print(f"{Fore.YELLOW}System shutting down......{Fore.RESET}")


