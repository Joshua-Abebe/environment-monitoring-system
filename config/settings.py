import os

from dotenv import load_dotenv

load_dotenv()

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE")
}


MONGO_URI = os.getenv("MONGO_URI")


NEO4J_CONFIG = {
    "uri": os.getenv("NEO4J_URI"),
    "user": os.getenv("NEO4J_USER"),
    "password": os.getenv("NEO4J_PASSWORD")
}


MQTT_CONFIG = {
    "broker": os.getenv("MQTT_BROKER"),
    "port": int(os.getenv("MQTT_PORT", 1883))
}