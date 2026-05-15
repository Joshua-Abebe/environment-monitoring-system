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

for _ in range(5):

    event = sensor.create_event()

    print(event)
