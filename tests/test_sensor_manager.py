"""Unit tests for publisher.sensor_manager.SensorManager.

Verifies sensor_loop() survives a failed publish instead of letting the
exception kill its daemon thread silently (which would make a sensor's
data permanently stop appearing on the dashboard with no visible error).
"""

from unittest.mock import MagicMock, patch

import pytest

from publisher.sensor_manager import SensorManager


def make_sensor():
    sensor = MagicMock()
    sensor.sensor_id = "s1"
    sensor.location = "Lab A"
    sensor.sensor_type = "temperature"
    sensor.interval = 5
    sensor.create_event.return_value = {"value": 1}
    return sensor


def test_sensor_loop_continues_after_publish_failure():
    """The first publish raises, the second succeeds. The loop must catch
    the exception, log it, sleep, and try again -- not exit the thread."""

    publisher = MagicMock()
    publisher.publish_event.side_effect = [Exception("broker hiccup"), None]

    manager = SensorManager(publisher)
    sensor = make_sensor()

    call_count = {"n": 0}

    def fake_sleep(_):
        call_count["n"] += 1
        if call_count["n"] >= 2:
            # deterministic way to stop the otherwise-infinite while loop
            raise StopIteration

    with patch("publisher.sensor_manager.time.sleep", side_effect=fake_sleep):
        with pytest.raises(StopIteration):
            manager.sensor_loop(sensor)

    assert publisher.publish_event.call_count == 2


def test_sensor_loop_keeps_sleeping_interval_after_failure():
    """Even when a publish fails, the loop should still sleep for the
    sensor's configured interval before retrying (no busy-looping)."""

    publisher = MagicMock()
    publisher.publish_event.side_effect = Exception("broker hiccup")

    manager = SensorManager(publisher)
    sensor = make_sensor()

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 1:
            raise StopIteration

    with patch("publisher.sensor_manager.time.sleep", side_effect=fake_sleep):
        with pytest.raises(StopIteration):
            manager.sensor_loop(sensor)

    assert sleep_calls == [sensor.interval]
