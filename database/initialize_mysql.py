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
    "Labratory"
)
mysql_handler.insert_location(
    "Server Room",
    "Infrastructure"
)


mysql_handler.insert_sensor(
    "S1",
    "temprature",
    "C",
    "Lab A"
)
mysql_handler.insert_sensor(
    "S2",
    "humidity",
    "%",
    "Lab A"
)
mysql_handler.insert_sensor(
    "S3",
    "air_quality",
    "AQI",
    "Server Room"
)