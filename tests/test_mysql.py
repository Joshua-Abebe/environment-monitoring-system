"""Unit tests for database.mysql_handler.MySQLHandler.

mysql.connector.connect is mocked so these tests run without a live
MySQL instance and without real credentials.
"""

from unittest.mock import MagicMock, patch

from database.mysql_handler import MySQLHandler


def make_handler():
    with patch("database.mysql_handler.mysql.connector.connect") as mock_connect:
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        handler = MySQLHandler(
            host="localhost",
            user="test_user",
            password="test_password",
            database="environment_monitoring"
        )

    return handler, mock_connection, mock_cursor


def test_initialize_tables_creates_event_metrics_table():
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchone.return_value = (0,)

    handler.initialize_tables()

    executed_sql = " ".join(
        call.args[0] for call in mock_cursor.execute.call_args_list
    )

    assert "event_metrics" in executed_sql
    assert "locations" in executed_sql
    assert "sensors" in executed_sql
    assert "readings" in executed_sql
    assert "alerts" in executed_sql
    mock_connection.commit.assert_called()


def test_initialize_tables_adds_neo4j_write_ms_column_when_missing():
    """Regression test: event_metrics may already exist from before the
    Neo4j write stage was timed. The migration must use a portable
    INFORMATION_SCHEMA existence check, not "ADD COLUMN IF NOT EXISTS"
    -- that clause doesn't exist in standard MySQL and raises error 1064."""
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchone.return_value = (0,)  # column does not exist yet

    handler.initialize_tables()

    executed_sql = " ".join(
        call.args[0] for call in mock_cursor.execute.call_args_list
    )

    assert "information_schema.COLUMNS" in executed_sql
    assert "ALTER TABLE event_metrics" in executed_sql
    assert "ADD COLUMN neo4j_write_ms FLOAT" in executed_sql
    assert "IF NOT EXISTS neo4j_write_ms" not in executed_sql


def test_initialize_tables_skips_alter_when_column_already_exists():
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchone.return_value = (1,)  # column already present

    handler.initialize_tables()

    executed_sql = " ".join(
        call.args[0] for call in mock_cursor.execute.call_args_list
    )

    assert "ALTER TABLE event_metrics" not in executed_sql


def test_initialize_tables_adds_sensor_simulation_columns_when_missing():
    """Regression test: `sensors` may already exist from before the
    publisher fleet became database-driven (see tests/run_publishers.py).
    Same portable INFORMATION_SCHEMA pattern as the neo4j_write_ms
    migration above -- standard MySQL has no "ADD COLUMN IF NOT EXISTS"."""
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchone.return_value = (0,)  # none of the columns exist yet

    handler.initialize_tables()

    executed_sql = " ".join(
        call.args[0] for call in mock_cursor.execute.call_args_list
    )

    assert "ALTER TABLE sensors ADD COLUMN min_value FLOAT" in executed_sql
    assert "ALTER TABLE sensors ADD COLUMN max_value FLOAT" in executed_sql
    assert "ALTER TABLE sensors ADD COLUMN initial_value FLOAT" in executed_sql
    assert "ALTER TABLE sensors ADD COLUMN interval_seconds INT" in executed_sql


def test_initialize_tables_skips_sensor_column_alter_when_already_exists():
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchone.return_value = (1,)  # columns already present

    handler.initialize_tables()

    executed_sql = " ".join(
        call.args[0] for call in mock_cursor.execute.call_args_list
    )

    assert "ALTER TABLE sensors" not in executed_sql


def test_insert_readings_commits():
    handler, mock_connection, mock_cursor = make_handler()

    handler.insert_readings(sensor_id="s1", value=28.5, timestamp="2026-05-17 15:30:00")

    mock_cursor.execute.assert_called_once()
    mock_connection.commit.assert_called_once()


def test_insert_event_metrics_passes_all_fields():
    handler, mock_connection, mock_cursor = make_handler()

    handler.insert_event_metrics(
        event_id="evt-1",
        received_at="2026-06-28 10:00:00",
        validated_at="2026-06-28 10:00:00",
        validation_ms=1.2,
        mysql_write_ms=3.4,
        neo4j_write_ms=2.1,
        mongo_write_ms=5.6,
        total_latency_ms=10.2
    )

    args, _ = mock_cursor.execute.call_args
    query, values = args

    assert "INSERT INTO event_metrics" in query
    assert values == ("evt-1", "2026-06-28 10:00:00", "2026-06-28 10:00:00", 1.2, 3.4, 2.1, 5.6, 10.2)
    mock_connection.commit.assert_called_once()


def test_insert_sensor_skips_when_location_missing():
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchone.return_value = None

    result = handler.insert_sensor(
        sensor_id="s99",
        sensor_type="temperature",
        unit="C",
        location_name="Nonexistent Room"
    )

    assert mock_cursor.execute.call_count == 1
    assert result is False


def test_insert_sensor_returns_true_when_row_created():
    """Regression test: INSERT IGNORE silently no-ops on a duplicate
    sensor_id (PRIMARY KEY). The dashboard's 'Add sensor' button used to
    always show a success message regardless of whether a row was
    actually inserted -- rowcount must be surfaced so callers can tell."""
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchone.return_value = (1,)  # location found
    mock_cursor.rowcount = 1

    result = handler.insert_sensor(
        sensor_id="s1",
        sensor_type="temperature",
        unit="C",
        location_name="Lab A"
    )

    assert result is True


def test_insert_sensor_returns_false_when_duplicate_id_ignored():
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchone.return_value = (1,)  # location found
    mock_cursor.rowcount = 0  # INSERT IGNORE no-op: sensor_id already exists

    result = handler.insert_sensor(
        sensor_id="s1",
        sensor_type="temperature",
        unit="C",
        location_name="Lab A"
    )

    assert result is False


def test_insert_sensor_persists_simulation_params():
    """Regression test: insert_sensor() must forward min_value/max_value/
    initial_value/interval_seconds into the INSERT -- these are what
    get_all_sensors() (and the publisher fleet) read back later."""
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchone.return_value = (1,)  # location found
    mock_cursor.rowcount = 1

    handler.insert_sensor(
        sensor_id="s1",
        sensor_type="temperature",
        unit="C",
        location_name="Lab A",
        min_value=20,
        max_value=40,
        initial_value=28,
        interval_seconds=5
    )

    insert_call = mock_cursor.execute.call_args_list[-1]
    query, values = insert_call.args

    assert "min_value" in query
    assert "max_value" in query
    assert "initial_value" in query
    assert "interval_seconds" in query
    assert values == ("s1", "temperature", "C", 1, 20, 40, 28, 5)


def test_insert_sensor_simulation_params_default_to_none():
    """Existing callers (older tests, catalog-only inserts) don't have to
    supply simulation params -- they should be stored as NULL, not crash."""
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchone.return_value = (1,)  # location found
    mock_cursor.rowcount = 1

    handler.insert_sensor(
        sensor_id="s1",
        sensor_type="temperature",
        unit="C",
        location_name="Lab A"
    )

    insert_call = mock_cursor.execute.call_args_list[-1]
    _, values = insert_call.args

    assert values == ("s1", "temperature", "C", 1, None, None, None, None)


def test_get_all_sensors_returns_list_of_dicts():
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchall.return_value = [
        ("s1", "temperature", "C", "Lab A", 20.0, 40.0, 28.0, 5),
        ("s2", "humidity", "%", "Lab A", 30.0, 90.0, 60.0, 7),
    ]

    sensors = handler.get_all_sensors()

    assert sensors == [
        {
            "sensor_id": "s1",
            "sensor_type": "temperature",
            "unit": "C",
            "location_name": "Lab A",
            "min_value": 20.0,
            "max_value": 40.0,
            "initial_value": 28.0,
            "interval_seconds": 5,
        },
        {
            "sensor_id": "s2",
            "sensor_type": "humidity",
            "unit": "%",
            "location_name": "Lab A",
            "min_value": 30.0,
            "max_value": 90.0,
            "initial_value": 60.0,
            "interval_seconds": 7,
        },
    ]

    executed_sql = mock_cursor.execute.call_args.args[0]
    assert "FROM sensors" in executed_sql
    assert "JOIN locations" in executed_sql


def test_backfill_sensor_simulation_defaults_skips_fully_set_rows():
    """A sensor that already has all four simulation columns set (e.g.
    one created through the dashboard's Add Sensor form) should not
    trigger an UPDATE at all -- COALESCE would no-op anyway, but skipping
    the round trip up front avoids touching rows that don't need it."""
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchall.return_value = [
        ("s1", "temperature", "C", "Lab A", 20.0, 40.0, 28.0, 5),
    ]

    updated = handler.backfill_sensor_simulation_defaults()

    assert updated == []
    executed_sql = " ".join(call.args[0] for call in mock_cursor.execute.call_args_list)
    assert "UPDATE sensors" not in executed_sql


def test_backfill_sensor_simulation_defaults_fills_nulls_with_type_preset():
    """Regression test for the real-world case that prompted this: s1-s6
    (and any sensor added before the simulation columns existed) sat with
    all four columns NULL forever, because INSERT IGNORE no-ops on an
    existing sensor_id -- it never updates the row's columns, even when
    initialize_mysql.py's seed calls pass real values. This backfill is
    what actually persists the type-aware defaults for those rows."""
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchall.return_value = [
        ("s1", "temperature", "C", "Lab A", None, None, None, None),
    ]

    updated = handler.backfill_sensor_simulation_defaults()

    assert updated == ["s1"]
    update_call = mock_cursor.execute.call_args_list[-1]
    query, values = update_call.args
    assert "UPDATE sensors" in query
    assert "COALESCE" in query
    assert values == (20, 40, 28, 5, "s1")  # temperature preset from config/sensor_defaults.py
    mock_connection.commit.assert_called()


def test_backfill_sensor_simulation_defaults_falls_back_to_generic_for_unknown_type():
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchall.return_value = [
        ("s99", "pressure", "hPa", "Lab A", None, None, None, None),
    ]

    updated = handler.backfill_sensor_simulation_defaults()

    assert updated == ["s99"]
    update_call = mock_cursor.execute.call_args_list[-1]
    _, values = update_call.args
    assert values == (0, 100, 50, 10, "s99")


def test_backfill_sensor_simulation_defaults_only_updates_rows_with_a_null_column():
    """Two sensors: one fully set (skipped), one partially NULL (backfilled).
    Only the partially-NULL one should produce an UPDATE."""
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.fetchall.return_value = [
        ("s1", "temperature", "C", "Lab A", 20.0, 40.0, 28.0, 5),
        ("s5", "humidity", "%", "Lab B", 30.0, 90.0, None, None),
    ]

    updated = handler.backfill_sensor_simulation_defaults()

    assert updated == ["s5"]
    update_call = mock_cursor.execute.call_args_list[-1]
    _, values = update_call.args
    # min/max come from the row itself (30/90), initial/interval from the
    # humidity preset, clamped/used as-is since 60 already falls in [30, 90]
    assert values == (30.0, 90.0, 60, 7, "s5")


def test_insert_location_returns_true_when_row_created():
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.rowcount = 1

    result = handler.insert_location("Lab C", "Lab")

    assert result is True


def test_insert_location_returns_false_when_duplicate_name_ignored():
    handler, mock_connection, mock_cursor = make_handler()
    mock_cursor.rowcount = 0  # INSERT IGNORE no-op: location_name already exists

    result = handler.insert_location("Lab A", "Lab")

    assert result is False


def test_delete_location_commits():
    handler, mock_connection, mock_cursor = make_handler()

    handler.delete_location("Lab A")

    args, _ = mock_cursor.execute.call_args
    query, values = args

    assert "DELETE FROM locations" in query
    assert values == ("Lab A",)
    mock_connection.commit.assert_called_once()


def test_delete_sensor_commits():
    handler, mock_connection, mock_cursor = make_handler()

    handler.delete_sensor("s1")

    args, _ = mock_cursor.execute.call_args
    query, values = args

    assert "DELETE FROM sensors" in query
    assert values == ("s1",)
    mock_connection.commit.assert_called_once()
