from database.mysql_handler import MySQLHandler
from config.settings import MYSQL_CONFIG

mysql_handler = MySQLHandler(
    **MYSQL_CONFIG
)

mysql_handler.initialize_tables()


mysql_handler.insert_location(
    "Lab A",
    "Laboratory"
)
mysql_handler.insert_location(
    "Server Room",
    "Infrastructure"
)
mysql_handler.insert_location(
    "Lab B",
    "Laboratory"
)
mysql_handler.insert_location(
    "Office 1",
    "Office"
)



mysql_handler.insert_sensor(
    "S1",
    "temperature",
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
mysql_handler.insert_sensor(
    "s4",
    "temperature",
    "C",
    "Lab B"
)
mysql_handler.insert_sensor(
    "s5",
    "humidity",
    "%",
    "Lab B"
)
mysql_handler.insert_sensor(
    "s6",
    "air_quality",
    "AQI",
    "Office 1"
)