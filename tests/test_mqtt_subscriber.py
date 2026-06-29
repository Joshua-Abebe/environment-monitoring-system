"""Unit tests for subscriber.mqtt_subscriber.MQTTSubscriber.

All database handlers and the paho-mqtt client are mocked, so these
tests exercise the real event-processing/alert logic without needing
a live broker, MySQL, MongoDB, or Neo4j instance.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from subscriber.mqtt_subscriber import MQTTSubscriber


class FakeMessage:
    def __init__(self, payload, topic="building/lab_a/temperature"):
        self.payload = json.dumps(payload).encode() if isinstance(payload, dict) else payload
        self.topic = topic


@pytest.fixture
def subscriber():
    with patch("subscriber.mqtt_subscriber.mqtt.Client"), \
         patch("subscriber.mqtt_subscriber.MySQLHandler") as mock_mysql_cls, \
         patch("subscriber.mqtt_subscriber.MongoDBHandler") as mock_mongo_cls, \
         patch("subscriber.mqtt_subscriber.Neo4jHandler") as mock_neo4j_cls:

        sub = MQTTSubscriber(broker="mosquitto", port=1883)

        # expose the mock instances for assertions
        sub.mysql_handler = mock_mysql_cls.return_value
        sub.mongodb_handler = mock_mongo_cls.return_value
        sub.neo4j_handler = mock_neo4j_cls.return_value

        yield sub


VALID_EVENT = {
    "sensor_id": "s1",
    "sensor_type": "temperature",
    "location": "Lab A",
    "unit": "C",
    "value": 28.5,
    "timestamp": "2026-06-28T10:00:00"
}


def test_validate_event_accepts_complete_event(subscriber):
    assert subscriber.validate_event(VALID_EVENT) is True


def test_validate_event_rejects_missing_field(subscriber):
    incomplete = {k: v for k, v in VALID_EVENT.items() if k != "value"}
    assert subscriber.validate_event(incomplete) is False


def test_on_message_inserts_reading_for_valid_event(subscriber):
    subscriber.on_message(None, None, FakeMessage(VALID_EVENT))

    subscriber.mysql_handler.insert_readings.assert_called_once()
    subscriber.mongodb_handler.insert_event.assert_called_once_with(VALID_EVENT)
    subscriber.mysql_handler.insert_event_metrics.assert_called_once()


def test_on_message_records_neo4j_write_ms_in_metrics(subscriber):
    """Regression test: the Neo4j write stage must be timed and passed to
    insert_event_metrics like mysql_write_ms/mongo_write_ms are, instead of
    being invisible inside total_latency_ms with no per-stage breakdown."""

    subscriber.on_message(None, None, FakeMessage(VALID_EVENT))

    _, kwargs = subscriber.mysql_handler.insert_event_metrics.call_args
    assert "neo4j_write_ms" in kwargs
    assert isinstance(kwargs["neo4j_write_ms"], float)


def test_on_message_records_zero_neo4j_write_ms_when_neo4j_unavailable(subscriber):
    subscriber.neo4j_handler = None

    subscriber.on_message(None, None, FakeMessage(VALID_EVENT))

    _, kwargs = subscriber.mysql_handler.insert_event_metrics.call_args
    assert kwargs["neo4j_write_ms"] == 0.0


def test_on_message_skips_invalid_event(subscriber):
    incomplete = {k: v for k, v in VALID_EVENT.items() if k != "sensor_id"}

    subscriber.on_message(None, None, FakeMessage(incomplete))

    subscriber.mysql_handler.insert_readings.assert_not_called()
    subscriber.mongodb_handler.insert_event.assert_not_called()


def test_on_message_does_not_crash_on_malformed_json(subscriber):
    bad_message = FakeMessage(b"not valid json")

    # should be caught internally and logged, not raised
    subscriber.on_message(None, None, bad_message)

    subscriber.mysql_handler.insert_readings.assert_not_called()


def test_temperature_alert_fires_above_threshold(subscriber):
    event = {**VALID_EVENT, "value": 40.0}

    subscriber.on_message(None, None, FakeMessage(event))

    subscriber.mysql_handler.insert_alert.assert_called_once()
    _, kwargs = subscriber.mysql_handler.insert_alert.call_args
    assert kwargs["severity"] == "HIGH"
    assert "Temperature" in kwargs["message"]


def test_temperature_alert_does_not_fire_below_threshold(subscriber):
    event = {**VALID_EVENT, "value": 25.0}

    subscriber.on_message(None, None, FakeMessage(event))

    subscriber.mysql_handler.insert_alert.assert_not_called()


def test_humidity_alert_fires_above_threshold(subscriber):
    event = {**VALID_EVENT, "sensor_type": "humidity", "value": 85.0, "unit": "%"}

    subscriber.on_message(None, None, FakeMessage(event))

    subscriber.mysql_handler.insert_alert.assert_called_once()
    _, kwargs = subscriber.mysql_handler.insert_alert.call_args
    assert kwargs["severity"] == "MEDIUM"


def test_air_quality_alert_fires_despite_space_typo_in_sensor_type(subscriber):
    """Regression test: a publisher sending 'air quality' (space) instead
    of 'air_quality' must still trigger the alert, thanks to sensor_type
    normalization in on_message."""

    event = {**VALID_EVENT, "sensor_type": "air quality", "value": 95.0, "unit": "AQI"}

    subscriber.on_message(None, None, FakeMessage(event))

    subscriber.mysql_handler.insert_alert.assert_called_once()
    _, kwargs = subscriber.mysql_handler.insert_alert.call_args
    assert "Air Quality" in kwargs["message"]


def test_air_quality_alert_does_not_fire_below_threshold(subscriber):
    event = {**VALID_EVENT, "sensor_type": "air_quality", "value": 50.0, "unit": "AQI"}

    subscriber.on_message(None, None, FakeMessage(event))

    subscriber.mysql_handler.insert_alert.assert_not_called()


def test_alert_does_not_repeat_while_still_over_threshold(subscriber):
    """Regression test: alerts are edge-triggered. A sensor that stays
    over threshold across several consecutive readings should only
    produce ONE alert row (on the first reading that crosses), not one
    per reading -- otherwise a single real excursion floods the Alerts
    page with duplicate rows for the same event."""
    event = {**VALID_EVENT, "value": 40.0}

    for _ in range(5):
        subscriber.on_message(None, None, FakeMessage(event))

    assert subscriber.mysql_handler.insert_alert.call_count == 1


def test_alert_fires_again_after_dropping_back_below_threshold(subscriber):
    """A second, genuinely separate excursion (value drops back under
    threshold, then crosses again later) must produce a second alert."""
    high_event = {**VALID_EVENT, "value": 40.0}
    normal_event = {**VALID_EVENT, "value": 25.0}

    subscriber.on_message(None, None, FakeMessage(high_event))    # alert #1
    subscriber.on_message(None, None, FakeMessage(normal_event))  # back to normal
    subscriber.on_message(None, None, FakeMessage(high_event))    # alert #2

    assert subscriber.mysql_handler.insert_alert.call_count == 2


def test_alert_debounce_state_is_tracked_per_sensor(subscriber):
    """Two different sensors crossing threshold independently must each
    get their own alert -- one sensor's "already alarming" state must
    not suppress another sensor's alert."""
    sensor_a = {**VALID_EVENT, "sensor_id": "s1", "value": 40.0}
    sensor_b = {**VALID_EVENT, "sensor_id": "s4", "value": 40.0}

    subscriber.on_message(None, None, FakeMessage(sensor_a))
    subscriber.on_message(None, None, FakeMessage(sensor_b))

    assert subscriber.mysql_handler.insert_alert.call_count == 2


def test_on_message_syncs_neo4j_graph_with_normalized_sensor_type(subscriber):
    event = {**VALID_EVENT, "sensor_type": "Air_Quality ", "value": 10.0}

    subscriber.on_message(None, None, FakeMessage(event))

    subscriber.neo4j_handler.create_sensor_relationships.assert_called_once_with(
        sensor_id="s1",
        sensor_type="air_quality",
        location="Lab A"
    )


def test_on_message_survives_when_neo4j_unavailable(subscriber):
    subscriber.neo4j_handler = None

    # must not raise, and the rest of the pipeline should still run
    subscriber.on_message(None, None, FakeMessage(VALID_EVENT))

    subscriber.mysql_handler.insert_readings.assert_called_once()


def test_on_message_survives_when_mongodb_write_fails(subscriber):
    """Regression test: a MongoDB outage (e.g. the container restarting,
    a dropped connection) must not take down the rest of the pipeline.
    insert_event_metrics should still run -- recording mongo_write_ms as
    0.0 for that event -- exactly like the existing Neo4j-unavailable
    case above, instead of the whole on_message call being swallowed by
    the broad except Exception at the bottom of the method."""
    subscriber.mongodb_handler.insert_event.side_effect = Exception("connection refused")

    subscriber.on_message(None, None, FakeMessage(VALID_EVENT))

    subscriber.mysql_handler.insert_readings.assert_called_once()
    subscriber.mysql_handler.insert_event_metrics.assert_called_once()
    _, kwargs = subscriber.mysql_handler.insert_event_metrics.call_args
    assert kwargs["mongo_write_ms"] == 0.0


def test_stop_disconnects_client_and_closes_all_handlers(subscriber):
    """Regression test: shutdown used to be a bare KeyboardInterrupt
    print with no cleanup at all, despite the README advertising
    'graceful shutdown handling'. stop() must actually disconnect the
    MQTT client and release every DB connection opened in __init__."""
    subscriber.stop()

    subscriber.client.disconnect.assert_called_once()
    subscriber.mysql_handler.connection.close.assert_called_once()
    subscriber.mongodb_handler.client.close.assert_called_once()
    subscriber.neo4j_handler.close.assert_called_once()


def test_stop_survives_when_neo4j_handler_is_none(subscriber):
    subscriber.neo4j_handler = None

    # must not raise
    subscriber.stop()

    subscriber.client.disconnect.assert_called_once()
    subscriber.mysql_handler.connection.close.assert_called_once()


def test_stop_survives_handler_close_failures(subscriber):
    """One handler failing to close (e.g. already-dropped connection)
    must not prevent the others from being cleaned up."""
    subscriber.mysql_handler.connection.close.side_effect = Exception("already closed")

    # must not raise
    subscriber.stop()

    subscriber.client.disconnect.assert_called_once()
    subscriber.mongodb_handler.client.close.assert_called_once()
    subscriber.neo4j_handler.close.assert_called_once()
