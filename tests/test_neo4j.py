"""Unit tests for database.neo4j_handler.Neo4jHandler.

neo4j.GraphDatabase.driver is mocked so these tests run without a live
Neo4j instance.
"""

from unittest.mock import MagicMock, patch

from database.neo4j_handler import Neo4jHandler


def make_handler():
    with patch("database.neo4j_handler.GraphDatabase") as mock_graphdb:
        mock_driver = MagicMock()
        mock_session = MagicMock()

        mock_graphdb.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session

        handler = Neo4jHandler(uri="bolt://localhost:7687", user="neo4j", password="test")

    return handler, mock_session


def test_create_sensor_relationships_runs_merge_query():
    handler, mock_session = make_handler()

    handler.create_sensor_relationships(
        sensor_id="s1",
        sensor_type="temperature",
        location="Lab A"
    )

    mock_session.run.assert_called_once()
    query, kwargs = mock_session.run.call_args.args[0], mock_session.run.call_args.kwargs

    assert "MERGE" in query
    assert kwargs == {"sensor_id": "s1", "sensor_type": "temperature", "location": "Lab A"}


def test_connect_rooms_runs_merge_query():
    handler, mock_session = make_handler()

    handler.connect_rooms("Lab A", "Server Room")

    mock_session.run.assert_called_once()
    query, kwargs = mock_session.run.call_args.args[0], mock_session.run.call_args.kwargs

    assert "CONNECTED_TO" in query
    # Regression guard: this must MERGE (not MATCH) the Location nodes.
    # The subscriber seeds room connections once at startup, before any
    # MQTT event has run create_sensor_relationships, so a MATCH-only
    # query would silently match nothing and never create the link.
    assert "MATCH" not in query
    assert kwargs == {"room1": "Lab A", "room2": "Server Room"}


def test_delete_room_relationship_runs_match_delete_query():
    handler, mock_session = make_handler()

    handler.delete_room_relationship("Lab A", "Server Room")

    mock_session.run.assert_called_once()
    query, kwargs = mock_session.run.call_args.args[0], mock_session.run.call_args.kwargs

    assert "CONNECTED_TO" in query
    assert "DELETE" in query
    assert kwargs == {"room1": "Lab A", "room2": "Server Room"}


def test_delete_sensor_runs_detach_delete_query():
    handler, mock_session = make_handler()

    handler.delete_sensor("s1")

    mock_session.run.assert_called_once()
    query, kwargs = mock_session.run.call_args.args[0], mock_session.run.call_args.kwargs

    assert "Sensor" in query
    assert "DETACH DELETE" in query
    assert kwargs == {"sensor_id": "s1"}


def test_delete_location_runs_detach_delete_query():
    handler, mock_session = make_handler()

    handler.delete_location("Lab A")

    mock_session.run.assert_called_once()
    query, kwargs = mock_session.run.call_args.args[0], mock_session.run.call_args.kwargs

    assert "Location" in query
    assert "DETACH DELETE" in query
    # Must OPTIONAL MATCH the sensors -- a room with no sensors yet must
    # still be deletable, so this can't be a plain MATCH that requires
    # at least one Sensor to exist.
    assert "OPTIONAL MATCH" in query
    assert "Sensor" in query
    assert kwargs == {"location_name": "Lab A"}


def test_close_closes_driver():
    with patch("database.neo4j_handler.GraphDatabase") as mock_graphdb:
        mock_driver = MagicMock()
        mock_graphdb.driver.return_value = mock_driver

        handler = Neo4jHandler(uri="bolt://localhost:7687", user="neo4j", password="test")
        handler.close()

        mock_driver.close.assert_called_once()
