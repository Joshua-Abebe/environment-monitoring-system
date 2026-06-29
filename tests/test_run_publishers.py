"""Unit tests for tests.run_publishers.load_sensors_from_catalog.

This is the function that lets the publisher fleet build itself from the
MySQL `sensors` catalog (via MySQLHandler.get_all_sensors()) instead of a
hardcoded list -- a sensor added through the dashboard's Manage page is
just another row here. No live MQTT or MySQL connection is needed: the
module only connects/publishes inside main(), guarded by
`if __name__ == "__main__":`, so importing it is side-effect free.
"""

from unittest.mock import MagicMock

from tests.run_publishers import (
    load_sensors_from_catalog,
    SENSOR_TYPE_DEFAULTS,
    DEFAULT_MIN_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_INTERVAL_SECONDS,
)


def make_mysql_handler(rows):
    handler = MagicMock()
    handler.get_all_sensors.return_value = rows
    return handler


def test_load_sensors_from_catalog_builds_sensor_per_row():
    handler = make_mysql_handler([
        {
            "sensor_id": "s1",
            "sensor_type": "temperature",
            "unit": "C",
            "location_name": "Lab A",
            "min_value": 20,
            "max_value": 40,
            "initial_value": 28,
            "interval_seconds": 5,
        },
    ])

    sensors = load_sensors_from_catalog(handler)

    assert len(sensors) == 1
    sensor = sensors[0]
    assert sensor.sensor_id == "s1"
    assert sensor.sensor_type == "temperature"
    assert sensor.location == "Lab A"
    assert sensor.unit == "C"
    assert sensor.min_value == 20
    assert sensor.max_value == 40
    assert sensor.current_value == 28
    assert sensor.interval == 5


def test_load_sensors_from_catalog_returns_empty_list_when_no_sensors():
    handler = make_mysql_handler([])

    assert load_sensors_from_catalog(handler) == []


def test_load_sensors_from_catalog_fills_defaults_for_missing_params():
    """Regression test: a sensor added through the dashboard before these
    columns existed (or inserted directly) would have NULL min_value/
    max_value/initial_value/interval_seconds. Without fallbacks, Sensor's
    constructor would receive None and explode on its first random walk
    step instead of just publishing with generic bounds."""
    handler = make_mysql_handler([
        {
            "sensor_id": "s99",
            "sensor_type": "pressure",
            "unit": "hPa",
            "location_name": "Lab A",
            "min_value": None,
            "max_value": None,
            "initial_value": None,
            "interval_seconds": None,
        },
    ])

    sensors = load_sensors_from_catalog(handler)

    assert len(sensors) == 1
    sensor = sensors[0]
    assert sensor.min_value == DEFAULT_MIN_VALUE
    assert sensor.max_value == DEFAULT_MAX_VALUE
    assert sensor.interval == DEFAULT_INTERVAL_SECONDS
    # initial_value defaults to the midpoint of the (possibly defaulted) bounds
    assert sensor.current_value == (DEFAULT_MIN_VALUE + DEFAULT_MAX_VALUE) / 2


def test_load_sensors_from_catalog_fills_only_missing_fields():
    """Partial NULLs (e.g. interval_seconds missing but bounds set) should
    only fall back for the missing field, not clobber the values that are
    actually present. "humidity" is a known type, so the missing fields
    fall back to its own preset (interval=7), not the flat generic
    default (10)."""
    handler = make_mysql_handler([
        {
            "sensor_id": "s5",
            "sensor_type": "humidity",
            "unit": "%",
            "location_name": "Lab B",
            "min_value": 30,
            "max_value": 90,
            "initial_value": None,
            "interval_seconds": None,
        },
    ])

    sensors = load_sensors_from_catalog(handler)

    sensor = sensors[0]
    assert sensor.min_value == 30
    assert sensor.max_value == 90
    assert sensor.current_value == 60  # humidity preset's initial_value, also the midpoint of 30/90 here
    assert sensor.interval == SENSOR_TYPE_DEFAULTS["humidity"]["interval_seconds"]


def test_load_sensors_from_catalog_uses_type_aware_defaults_for_known_types():
    """A sensor of a known type (temperature/humidity/air_quality) with
    missing simulation params should fall back to that type's own preset
    range -- not the flat generic default -- so e.g. a new temperature
    sensor doesn't end up wandering a 0-100C range and constantly
    tripping the >35C alert."""
    handler = make_mysql_handler([
        {
            "sensor_id": "s8",
            "sensor_type": "temperature",
            "unit": "C",
            "location_name": "Lab A",
            "min_value": None,
            "max_value": None,
            "initial_value": None,
            "interval_seconds": None,
        },
    ])

    sensors = load_sensors_from_catalog(handler)

    sensor = sensors[0]
    preset = SENSOR_TYPE_DEFAULTS["temperature"]
    assert sensor.min_value == preset["min_value"]
    assert sensor.max_value == preset["max_value"]
    assert sensor.current_value == preset["initial_value"]
    assert sensor.interval == preset["interval_seconds"]


def test_load_sensors_from_catalog_clamps_type_preset_initial_to_custom_bounds():
    """If a known type's bounds are customized narrower than its own
    preset range, a missing initial_value should still land inside the
    sensor's *actual* bounds, not the type preset's -- Sensor's
    constructor doesn't validate this itself."""
    handler = make_mysql_handler([
        {
            "sensor_id": "s9",
            "sensor_type": "humidity",
            "unit": "%",
            "location_name": "Lab A",
            "min_value": 10,
            "max_value": 20,
            "initial_value": None,
            "interval_seconds": None,
        },
    ])

    sensors = load_sensors_from_catalog(handler)

    sensor = sensors[0]
    assert sensor.min_value == 10
    assert sensor.max_value == 20
    assert sensor.current_value == 20  # humidity's preset initial (60) clamped into [10, 20]
