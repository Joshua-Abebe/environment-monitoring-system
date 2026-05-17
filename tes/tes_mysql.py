from database.mysql_handler import MySQLHandler

mysql_handler = MySQLHandler(
    host="localhost",
    user="abc",
    password="projects5555",
    database="environment_monitoring"
)

mysql_handler.initialize_tables()

mysql_handler.insert_location(
    "Lab A",
    "temperature"
)


mysql_handler.insert_sensor(
    sensor_id="s1",
    sensor_type="temperature",
    unit="C",
    location_name="Lab A"
)

mysql_handler.insert_readings(
    sensor_id="s1",
    value=28.5,
    timestamp="2026-05-17 15:30:00"
)

