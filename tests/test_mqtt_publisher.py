"""Unit tests for publisher.mqtt_publisher.MQTTPublisher.

The real paho-mqtt Client is replaced with a mock so these tests run
without a live Mosquitto broker.
"""

import json
from unittest.mock import MagicMock, patch

from publisher.mqtt_publisher import MQTTPublisher
from publisher.sensor import Sensor


@patch("publisher.mqtt_publisher.mqtt.Client")
def test_connect_calls_client_connect(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    publisher = MQTTPublisher(broker="mosquitto", port=1883)
    publisher.connect()

    mock_client.connect.assert_called_once_with("mosquitto", 1883)


@patch("publisher.mqtt_publisher.mqtt.Client")
def test_connect_starts_network_loop(mock_client_cls):
    """Regression test: without loop_start(), paho-mqtt never services
    its socket, so it can't send the periodic PINGREQ keepalive. The
    broker then drops the connection ~1.5x the keepalive interval after
    connect, and every publish() after that silently fails on a dead
    socket."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    publisher = MQTTPublisher(broker="mosquitto", port=1883)
    publisher.connect()

    mock_client.loop_start.assert_called_once()


@patch("publisher.mqtt_publisher.mqtt.Client")
def test_disconnect_stops_loop_and_disconnects_client(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    publisher = MQTTPublisher(broker="mosquitto", port=1883)
    publisher.disconnect()

    mock_client.loop_stop.assert_called_once()
    mock_client.disconnect.assert_called_once()


@patch("publisher.mqtt_publisher.mqtt.Client")
def test_publish_event_sends_json_payload(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    publisher = MQTTPublisher(broker="mosquitto", port=1883)

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
    event = sensor.create_event()
    topic = "building/lab_a/temperature"

    publisher.publish_event(topic, event)

    mock_client.publish.assert_called_once()
    called_topic, called_payload = mock_client.publish.call_args[0]

    assert called_topic == topic
    assert json.loads(called_payload) == event


@patch("publisher.mqtt_publisher.mqtt.Client")
def test_client_created_with_callback_api_version_2(mock_client_cls):
    import paho.mqtt.client as mqtt

    MQTTPublisher(broker="mosquitto", port=1883)

    mock_client_cls.assert_called_once_with(mqtt.CallbackAPIVersion.VERSION2)
