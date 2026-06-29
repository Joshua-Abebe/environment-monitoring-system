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



# Simulation params (min/max/initial/interval) mirror the hardcoded
# defaults that used to live solely in tests/run_publishers.py. Seeding
# them here means the publisher fleet -- which now reads its sensor list
# from this same `sensors` table via get_all_sensors() -- reproduces the
# original s1-s6 behavior on a fresh install with no other config needed.
mysql_handler.insert_sensor(
    "s1",
    "temperature",
    "C",
    "Lab A",
    min_value=20,
    max_value=40,
    initial_value=28,
    interval_seconds=5
)
mysql_handler.insert_sensor(
    "s2",
    "humidity",
    "%",
    "Lab A",
    min_value=30,
    max_value=90,
    initial_value=60,
    interval_seconds=7
)
mysql_handler.insert_sensor(
    "s3",
    "air_quality",
    "AQI",
    "Server Room",
    min_value=10,
    max_value=150,
    initial_value=40,
    interval_seconds=10
)
mysql_handler.insert_sensor(
    "s4",
    "temperature",
    "C",
    "Lab B",
    min_value=20,
    max_value=40,
    initial_value=27,
    interval_seconds=5
)
mysql_handler.insert_sensor(
    "s5",
    "humidity",
    "%",
    "Lab B",
    min_value=30,
    max_value=90,
    # was 70, which sits exactly ON the >70 humidity alert threshold --
    # baseline noise alone would constantly tip it over. 55 gives it the
    # same kind of headroom s2 (Lab A humidity, initial=60) already has.
    initial_value=55,
    interval_seconds=7
)
mysql_handler.insert_sensor(
    "s6",
    "air_quality",
    "AQI",
    "Office 1",
    min_value=10,
    max_value=150,
    initial_value=45,
    interval_seconds=9
)
