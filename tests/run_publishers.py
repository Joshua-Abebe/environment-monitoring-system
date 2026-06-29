from publisher.sensor import Sensor
from publisher.mqtt_publisher import MQTTPublisher
from publisher.sensor_manager import SensorManager
from config.settings import MQTT_CONFIG, MYSQL_CONFIG
from database.mysql_handler import MySQLHandler
from config.logger import logger

from colorama import Fore, init
init(autoreset=True)

# Fallback simulation parameters used when a sensor's catalog row is
# missing one or more of min_value/max_value/initial_value/interval_seconds
# -- e.g. a sensor inserted directly into MySQL, or one added through the
# dashboard's Manage page before these columns existed. Without these
# defaults a sensor with a NULL column would crash Sensor's constructor
# instead of just publishing somewhat-generic data.
#
# For a known sensor_type (temperature/humidity/air_quality), the
# type-specific preset in SENSOR_TYPE_DEFAULTS is used instead of the flat
# generic numbers below -- a temperature sensor falling back to a 0-100
# range would constantly trip the >35C alert, even though that same 0-100
# range happens to look reasonable for humidity. The generic constants
# remain only for a genuinely unknown/custom sensor_type, where no zone
# information exists to be type-aware about.
from config.sensor_defaults import (
    SENSOR_TYPE_DEFAULTS,
    DEFAULT_MIN_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_INTERVAL_SECONDS,
)


def load_sensors_from_catalog(mysql_handler):
    """Build the live Sensor fleet from the MySQL `sensors` catalog
    instead of a hardcoded list, so a sensor added through the
    dashboard's Manage page actually gets simulated once this process
    (re)starts -- see insert_sensor()/get_all_sensors() in
    database/mysql_handler.py.

    Falls back to that sensor_type's preset in SENSOR_TYPE_DEFAULTS for
    any row missing min_value/max_value/initial_value/interval_seconds
    (NULL), or to the flat DEFAULT_* constants if the type isn't one of
    the known presets. A missing initial_value defaults to the type
    preset's own initial_value (or the midpoint of the effective min/max
    for an unknown type), then gets clamped into [min_value, max_value]
    in case a customized min/max on the row falls outside the preset's
    range.
    """

    sensors = []

    for row in mysql_handler.get_all_sensors():

        type_defaults = SENSOR_TYPE_DEFAULTS.get(row["sensor_type"], {})

        min_value = row["min_value"] if row["min_value"] is not None else type_defaults.get("min_value", DEFAULT_MIN_VALUE)
        max_value = row["max_value"] if row["max_value"] is not None else type_defaults.get("max_value", DEFAULT_MAX_VALUE)
        interval = row["interval_seconds"] if row["interval_seconds"] is not None else type_defaults.get("interval_seconds", DEFAULT_INTERVAL_SECONDS)

        if row["initial_value"] is not None:
            initial_value = row["initial_value"]
        elif "initial_value" in type_defaults:
            initial_value = type_defaults["initial_value"]
        else:
            initial_value = (min_value + max_value) / 2

        # A type preset's initial_value (or a manually-entered one) could
        # land outside this sensor's own min/max if those were
        # customized. Sensor.generate_values() would self-correct on its
        # first reading anyway, but starting inside bounds avoids a
        # misleadingly out-of-range first event.
        initial_value = max(min_value, min(max_value, initial_value))

        sensors.append(Sensor(
            sensor_id=row["sensor_id"],
            sensor_type=row["sensor_type"],
            location=row["location_name"],
            unit=row["unit"],
            min_value=min_value,
            max_value=max_value,
            initial_value=initial_value,
            interval=interval
        ))

    return sensors


def main():

    publisher = MQTTPublisher(**MQTT_CONFIG)
    publisher.connect()

    manager = SensorManager(publisher)

    mysql_handler = MySQLHandler(**MYSQL_CONFIG)

    sensors = load_sensors_from_catalog(mysql_handler)

    if not sensors:
        logger.warning(f"{Fore.RED}No sensors found in the MySQL catalog -- nothing to publish{Fore.RESET}")

    for sensor in sensors:
        manager.add_sensor(sensor)
        logger.info(f"Loaded {sensor.sensor_id} ({sensor.sensor_type} @ {sensor.location}) from catalog")

    try:
        manager.start_all_sensors()

    except KeyboardInterrupt:
        print(f"{Fore.YELLOW}System shutting down......{Fore.RESET}")
        publisher.disconnect()


if __name__ == "__main__":
    main()
