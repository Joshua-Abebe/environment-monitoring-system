"""Unit tests for database.mongodb_handler.MongoDBHandler.

pymongo's MongoClient is mocked so these tests run without a live
MongoDB instance.
"""

from unittest.mock import MagicMock, patch

from database.mongodb_handler import MongoDBHandler


@patch("database.mongodb_handler.MongoClient")
def test_handler_uses_environment_monitoring_database(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    MongoDBHandler(uri="mongodb://localhost:27017")

    mock_client.__getitem__.assert_called_with("environment_monitoring")


@patch("database.mongodb_handler.MongoClient")
def test_insert_event_writes_to_sensor_events_collection(mock_client_cls):
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    mock_client_cls.return_value = mock_client
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_collection

    handler = MongoDBHandler(uri="mongodb://localhost:27017")

    sample_event = {
        "sensor_id": "s1",
        "sensor_type": "temperature",
        "location": "Lab A",
        "unit": "C",
        "value": 28.5,
        "timestamp": "2026-05-18T15:30:00"
    }

    handler.insert_event(sample_event)

    mock_db.__getitem__.assert_called_with("sensor_events")
    mock_collection.insert_one.assert_called_once_with(sample_event)
