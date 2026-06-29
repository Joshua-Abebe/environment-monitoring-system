"""Unit tests for the analytics CLI tool's close() methods.

Each Analytics class wraps one of the project's DB handlers and is held
as a long-lived object for the duration of the analytics_menu.py
interactive loop. Regression test: these classes used to have no way to
release their connection at all, so exiting the menu (or finishing a
script that used them) leaked a MySQL/MongoDB/Neo4j connection every
time. The handler/client classes are mocked so these tests run without
any live database.
"""

from unittest.mock import MagicMock, patch

from analytics.mysql_analytics import MySQLAnalytics
from analytics.mongodb_analytics import MongoDBAnalytics
from analytics.neo4j_analytics import Neo4jAnalytics


def test_mysql_analytics_close_closes_connection():
    with patch("analytics.mysql_analytics.MySQLHandler") as mock_handler_cls:
        mock_handler = MagicMock()
        mock_handler_cls.return_value = mock_handler

        analytics = MySQLAnalytics()
        analytics.close()

        mock_handler.connection.close.assert_called_once()


def test_mongodb_analytics_close_closes_client():
    with patch("analytics.mongodb_analytics.MongoDBHandler") as mock_handler_cls:
        mock_handler = MagicMock()
        mock_handler_cls.return_value = mock_handler

        analytics = MongoDBAnalytics()
        analytics.close()

        mock_handler.client.close.assert_called_once()


def test_neo4j_analytics_close_closes_driver():
    with patch("analytics.neo4j_analytics.Neo4jHandler") as mock_handler_cls:
        mock_handler = MagicMock()
        mock_handler_cls.return_value = mock_handler

        analytics = Neo4jAnalytics()
        analytics.close()

        mock_handler.close.assert_called_once()


def test_mysql_analytics_avg_temperature_query_uses_single_quotes():
    """Regression guard: WHERE s.sensor_type = "temperature" used double
    quotes around a string literal, which is non-portable SQL (only
    valid under MySQL's non-default ANSI_QUOTES sql_mode, where double
    quotes are treated as identifier quoting instead of string quoting).
    Standard single-quoted string literals work everywhere."""
    with patch("analytics.mysql_analytics.MySQLHandler") as mock_handler_cls:
        mock_handler = MagicMock()
        mock_handler.cursor.fetchall.return_value = []
        mock_handler_cls.return_value = mock_handler

        analytics = MySQLAnalytics()
        analytics.avg_temperature_per_room()

        query = mock_handler.cursor.execute.call_args[0][0]
        assert "'temperature'" in query
        assert '"temperature"' not in query
