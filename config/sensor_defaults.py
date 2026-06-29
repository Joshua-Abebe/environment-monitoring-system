"""Shared per-sensor-type simulation presets.

Both the dashboard's Add Sensor form (dashboard/app.py) and the publisher
fleet (tests/run_publishers.py) read from here, so a sensor's simulated
range stays sensible for its type whether it was hand-picked in the form
or fell back to a default because a catalog row came back with NULL
simulation columns. Keeping one shared source means the two can't drift
out of sync with each other.

These mirror the original s1-s6 seed values (database/initialize_mysql.py)
and, in turn, the alert thresholds in subscriber/mqtt_subscriber.py's
three Normal / Warning / Danger zones:

    Type          Normal   Warning   Danger
    temperature   < 30     30-35     > 35
    humidity      < 70     --        > 70
    air_quality   < 50     50-80     > 80

Each preset's initial_value sits inside Normal, and its max_value reaches
past Danger -- so a sensor mostly reads Normal, but the existing rare
"anomaly" mechanism in publisher/sensor.py can occasionally carry it into
Warning/Danger, which is what makes alerts believable instead of either
constant or impossible.
"""

SENSOR_TYPE_DEFAULTS = {
    "temperature": {"min_value": 20, "max_value": 40, "initial_value": 28, "interval_seconds": 5},
    "humidity": {"min_value": 30, "max_value": 90, "initial_value": 60, "interval_seconds": 7},
    "air_quality": {"min_value": 10, "max_value": 150, "initial_value": 40, "interval_seconds": 10},
}

# Generic fallback for a sensor type that isn't one of the three above
# (e.g. a genuinely custom/unknown type). No zone information exists for
# it, so these are intentionally plain/unopinionated.
DEFAULT_MIN_VALUE = 0
DEFAULT_MAX_VALUE = 100
DEFAULT_INITIAL_VALUE = 50
DEFAULT_INTERVAL_SECONDS = 10
