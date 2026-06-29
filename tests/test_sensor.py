"""Unit tests for publisher.sensor.Sensor -- no broker/DB needed."""

import random
from datetime import datetime
from unittest.mock import patch

import pytest

from publisher.sensor import Sensor


@pytest.fixture
def sensor():
    return Sensor(
        sensor_id="s1",
        sensor_type="temperature",
        location="Lab A",
        unit="C",
        min_value=20,
        max_value=40,
        initial_value=28,
        interval=5
    )


def test_generate_values_stays_within_bounds(sensor):
    for _ in range(2000):
        value = sensor.generate_values()
        assert sensor.min_value <= value <= sensor.max_value
        assert sensor.min_value <= sensor.current_value <= sensor.max_value


def test_generate_values_rounds_to_two_decimals(sensor):
    value = sensor.generate_values()
    assert value == round(value, 2)


def test_create_event_contains_required_fields(sensor):
    event = sensor.create_event()

    for field in ("sensor_id", "sensor_type", "location", "value", "unit", "timestamp"):
        assert field in event

    assert event["sensor_id"] == "s1"
    assert event["sensor_type"] == "temperature"
    assert event["location"] == "Lab A"
    assert event["unit"] == "C"


def test_create_event_timestamp_is_isoformat(sensor):
    event = sensor.create_event()
    parsed = datetime.fromisoformat(event["timestamp"])
    assert isinstance(parsed, datetime)


def test_create_event_value_matches_generated_value(sensor):
    event = sensor.create_event()
    assert event["value"] == round(sensor.current_value, 2)


def test_clamping_when_value_pushed_above_max():
    sensor = Sensor(
        sensor_id="s2",
        sensor_type="humidity",
        location="Lab A",
        unit="%",
        min_value=30,
        max_value=90,
        initial_value=85,
        interval=7
    )

    sensor.current_value = 500
    value = sensor.generate_values()

    assert value <= 90


def test_normal_value_defaults_to_initial_value(sensor):
    assert sensor.normal_value == 28


def test_generate_values_reverts_toward_normal_value_with_no_noise_or_anomaly():
    """Regression test: the walk must be mean-reverting, not a pure
    unbiased random walk. With noise and anomaly forced to zero, a value
    sitting away from normal_value should move measurably back toward it
    every step (old behaviour had no such pull at all)."""
    sensor = Sensor(
        sensor_id="s1",
        sensor_type="temperature",
        location="Lab A",
        unit="C",
        min_value=0,
        max_value=100,
        initial_value=50,
        interval=5
    )
    sensor.current_value = 80  # far from normal_value (50)

    with patch("publisher.sensor.random.uniform", return_value=0.0), \
         patch("publisher.sensor.random.random", return_value=1.0):  # 1.0 >= anomaly_probability, so no anomaly fires
        sensor.generate_values()

    # pull = (50 - 80) * 0.15 = -4.5, noise/anomaly forced to 0
    assert sensor.current_value == pytest.approx(75.5)


def test_generate_values_anomaly_can_push_toward_max():
    """Regression test: an anomaly event should be able to push the value
    sharply toward max_value -- this is what lets occasional alert-worthy
    excursions happen at all, since reversion+noise alone keeps the walk
    tightly clustered near normal_value."""
    sensor = Sensor(
        sensor_id="s1",
        sensor_type="air_quality",
        location="Server Room",
        unit="AQI",
        min_value=10,
        max_value=150,
        initial_value=40,
        interval=10
    )

    call_count = {"random_calls": 0}

    def fake_random():
        # First call checks "did an anomaly fire" -- force yes.
        # Second call picks high/low extreme -- force "toward max".
        call_count["random_calls"] += 1
        return 0.0

    with patch("publisher.sensor.random.uniform", side_effect=[0.0, 0.6]), \
         patch("publisher.sensor.random.random", side_effect=fake_random):
        value = sensor.generate_values()

    # anomaly pushed current_value well above its starting point of 40
    assert value > 40


def test_anomaly_probability_is_rare():
    """Sanity check on the tuned constant: anomalies should be rare
    (on the order of ~1 in 1000 readings), not a frequent occurrence --
    otherwise the walk is back to producing constant alerts."""
    sensor = Sensor(
        sensor_id="s1",
        sensor_type="temperature",
        location="Lab A",
        unit="C",
        min_value=20,
        max_value=40,
        initial_value=28,
        interval=5
    )
    assert 0 < sensor.anomaly_probability <= 0.01


def test_empirical_alert_crossing_rate_is_occasional_not_constant():
    """Statistical check, not a strict unit test: run the walk for a long
    simulated stretch and confirm it crosses the humidity alert threshold
    (>70) only occasionally -- a small fraction of readings, not the
    majority. This is the concrete behaviour the realism fix exists for."""
    random.seed(42)
    sensor = Sensor(
        sensor_id="s5",
        sensor_type="humidity",
        location="Lab B",
        unit="%",
        min_value=30,
        max_value=90,
        initial_value=55,
        interval=7
    )

    THRESHOLD = 70
    readings = 5000
    over_threshold = sum(1 for _ in range(readings) if sensor.generate_values() > THRESHOLD)

    fraction_over = over_threshold / readings
    # "few, not very few" -- expect well under 10% of readings to be
    # alert-worthy, but not literally zero either.
    assert 0 < fraction_over < 0.10
