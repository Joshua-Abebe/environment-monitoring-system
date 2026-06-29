import mysql.connector
from config.logger import logger

from colorama import Fore, init
init(autoreset=True)

class MySQLHandler:

    def __init__(self, host, user, password, database):

        self.connection = mysql.connector.connect(
            host = host,
            user = user,
            password = password,
            database = database
        )

        self.cursor = self.connection.cursor()

        logger.info(f"{Fore.GREEN}Connected to MySQL{Fore.RESET}")


    def initialize_tables(self):

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS locations(
                location_id INT AUTO_INCREMENT PRIMARY KEY,
                location_name VARCHAR(100) UNIQUE,
                location_type VARCHAR(100)
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensors(
                sensor_id VARCHAR(50) PRIMARY KEY,
                sensor_type VARCHAR(50),
                unit VARCHAR(20),
                location_id INT,
                FOREIGN KEY (location_id)
                    REFERENCES locations(location_id)
                    ON DELETE CASCADE
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS readings(
                reading_id INT AUTO_INCREMENT PRIMARY KEY,
                sensor_id VARCHAR(50),
                value FLOAT,
                timestamp DATETIME,
                FOREIGN KEY (sensor_id)
                    REFERENCES sensors(sensor_id)
                    ON DELETE CASCADE
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts(
                alert_id INT AUTO_INCREMENT PRIMARY KEY,
                sensor_id VARCHAR(50),
                severity VARCHAR(20),
                message TEXT,
                timestamp DATETIME,
                FOREIGN KEY (sensor_id)
                    REFERENCES sensors(sensor_id)
                    ON DELETE CASCADE
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_metrics(
                event_id VARCHAR(64) PRIMARY KEY,
                received_at DATETIME,
                validated_at DATETIME,
                validation_ms FLOAT,
                mysql_write_ms FLOAT,
                mongo_write_ms FLOAT,
                total_latency_ms FLOAT
            )
        """)

        # Additive, idempotent migration for installs where event_metrics
        # already existed before the Neo4j write stage was timed.
        #
        # NOTE: standard MySQL (unlike MariaDB) has no "ADD COLUMN IF NOT
        # EXISTS" clause -- using it raises error 1064 ("You have an error
        # in your SQL syntax"). The portable way to do this on real MySQL
        # is to check INFORMATION_SCHEMA first and only ALTER if the
        # column is actually missing.
        self.cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'event_metrics'
              AND COLUMN_NAME = 'neo4j_write_ms'
        """)
        column_exists = self.cursor.fetchone()[0] > 0

        if not column_exists:
            self.cursor.execute("""
                ALTER TABLE event_metrics
                ADD COLUMN neo4j_write_ms FLOAT
            """)

        # Additive, idempotent migration for installs where `sensors`
        # already existed before the publisher fleet became database-
        # driven (see tests/run_publishers.py). These simulation bounds
        # are what let a sensor added through the dashboard's Manage page
        # actually get simulated readings once the publisher restarts --
        # without them the publisher has no idea what range to generate
        # values in or how often to publish for a sensor it didn't
        # define itself.
        for column_name, ddl_type in (
            ("min_value", "FLOAT"),
            ("max_value", "FLOAT"),
            ("initial_value", "FLOAT"),
            ("interval_seconds", "INT"),
        ):
            self.cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'sensors'
                  AND COLUMN_NAME = %s
            """, (column_name,))
            column_exists = self.cursor.fetchone()[0] > 0

            if not column_exists:
                self.cursor.execute(f"ALTER TABLE sensors ADD COLUMN {column_name} {ddl_type}")

        self.connection.commit()

        logger.info(f"{Fore.GREEN}MySQL tables initialized{Fore.RESET}")


    def insert_location(self, location_name, location_type):

        query = """
            INSERT IGNORE INTO locations(
                location_name,
                location_type
            )
            VALUES (%s, %s)
        """

        values = (location_name, location_type)

        self.cursor.execute(query, values)

        self.connection.commit()

        # INSERT IGNORE silently no-ops on a duplicate location_name
        # (UNIQUE constraint) -- rowcount tells the caller whether a new
        # row was actually created, so the dashboard doesn't report
        # success for a no-op.
        return self.cursor.rowcount > 0


    def insert_sensor(
            self,
            sensor_id,
            sensor_type,
            unit,
            location_name,
            min_value=None,
            max_value=None,
            initial_value=None,
            interval_seconds=None
    ):

        #find locaiton id
        self.cursor.execute("""
            SELECT location_id
            FROM locations
            WHERE location_name = %s
        """, (location_name,))

        result = self.cursor.fetchone()

        if result is None:
            logger.warning(f"{Fore.RED}Location not found: {location_name}{Fore.RESET}")
            return False

        location_id = result[0]

        # min_value/max_value/initial_value/interval_seconds are the
        # simulation parameters the publisher fleet reads back via
        # get_all_sensors() to decide what range of values to generate
        # and how often to publish for this sensor. They're optional
        # (None) so callers that only care about the catalog entry --
        # e.g. existing tests -- don't have to supply them.
        query = """
            INSERT IGNORE INTO sensors(
                sensor_id,
                sensor_type,
                unit,
                location_id,
                min_value,
                max_value,
                initial_value,
                interval_seconds
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            sensor_id,
            sensor_type,
            unit,
            location_id,
            min_value,
            max_value,
            initial_value,
            interval_seconds,
        )

        self.cursor.execute(query, values)

        self.connection.commit()

        # INSERT IGNORE silently no-ops on a duplicate sensor_id (PRIMARY
        # KEY) -- rowcount tells the caller whether a new row was
        # actually created, so the dashboard doesn't report success for
        # a no-op.
        return self.cursor.rowcount > 0


    def backfill_sensor_simulation_defaults(self):
        """One-time (but safe to re-run) backfill for sensors whose
        min_value/max_value/initial_value/interval_seconds are still
        NULL -- e.g. a sensor added through the dashboard's Manage page,
        or seeded directly, before these columns existed.

        load_sensors_from_catalog() (tests/run_publishers.py) already
        covers this with an in-memory, type-aware fallback at publisher
        startup, so the publisher works correctly either way -- but the
        catalog row itself stays NULL forever unless something writes it
        back. This computes the same type-aware values (see
        config/sensor_defaults.py) and persists them, so the table
        itself shows real numbers instead of NULL.

        Uses COALESCE so it only ever fills in a column that's actually
        NULL -- a value someone already set (through the dashboard's Add
        Sensor form, for instance) is never overwritten. Safe to run
        more than once.

        Returns the list of sensor_ids that were updated.
        """
        from config.sensor_defaults import (
            SENSOR_TYPE_DEFAULTS,
            DEFAULT_MIN_VALUE,
            DEFAULT_MAX_VALUE,
            DEFAULT_INTERVAL_SECONDS,
        )

        updated = []

        for row in self.get_all_sensors():
            if all(
                row[column] is not None
                for column in ("min_value", "max_value", "initial_value", "interval_seconds")
            ):
                continue  # nothing missing -- COALESCE would no-op anyway, skip the round trip

            type_defaults = SENSOR_TYPE_DEFAULTS.get(row["sensor_type"], {})

            min_value = row["min_value"] if row["min_value"] is not None else type_defaults.get("min_value", DEFAULT_MIN_VALUE)
            max_value = row["max_value"] if row["max_value"] is not None else type_defaults.get("max_value", DEFAULT_MAX_VALUE)
            interval = row["interval_seconds"] if row["interval_seconds"] is not None else type_defaults.get("interval_seconds", DEFAULT_INTERVAL_SECONDS)

            if row["initial_value"] is not None:
                initial_value = row["initial_value"]
            elif "initial_value" in type_defaults:
                initial_value = type_defaults["initial_value"]
            else:
                initial_value = (min_value + max_value) / 2

            # Clamp in case this sensor's own min/max (if set) falls
            # outside the type preset's initial_value -- same safeguard
            # load_sensors_from_catalog() applies at runtime.
            initial_value = max(min_value, min(max_value, initial_value))

            self.cursor.execute("""
                UPDATE sensors
                SET min_value = COALESCE(min_value, %s),
                    max_value = COALESCE(max_value, %s),
                    initial_value = COALESCE(initial_value, %s),
                    interval_seconds = COALESCE(interval_seconds, %s)
                WHERE sensor_id = %s
            """, (min_value, max_value, initial_value, interval, row["sensor_id"]))

            updated.append(row["sensor_id"])

        self.connection.commit()

        return updated


    def get_all_sensors(self):
        """Return every sensor's full catalog entry, including its
        simulation parameters, as a list of dicts. This is what the
        publisher fleet (tests/run_publishers.py) reads at startup to
        build its Sensor objects from the database instead of a
        hardcoded Python list -- so a sensor added through the
        dashboard's Manage page can actually start publishing once the
        publisher container restarts.
        """

        self.cursor.execute("""
            SELECT s.sensor_id, s.sensor_type, s.unit, l.location_name,
                   s.min_value, s.max_value, s.initial_value, s.interval_seconds
            FROM sensors s
            JOIN locations l ON s.location_id = l.location_id
        """)

        columns = (
            "sensor_id",
            "sensor_type",
            "unit",
            "location_name",
            "min_value",
            "max_value",
            "initial_value",
            "interval_seconds",
        )

        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]


    def insert_readings(
            self,
            sensor_id,
            value,
            timestamp
    ):

        query = """
            INSERT INTO readings(
                sensor_id,
                value,
                timestamp
            )
            VALUES (%s, %s, %s)
        """

        values = (sensor_id, value, timestamp)

        self.cursor.execute(query, values)

        self.connection.commit()


    def insert_alert(
            self,
            sensor_id,
            severity,
            message,
            timestamp
    ):

        query = """
            INSERT INTO alerts(
                sensor_id,
                severity,
                message,
                timestamp
            )
            VALUES (%s, %s, %s, %s)
        """

        values = (sensor_id, severity, message, timestamp)

        self.cursor.execute(query, values)

        self.connection.commit()


    def insert_event_metrics(
            self,
            event_id,
            received_at,
            validated_at,
            validation_ms,
            mysql_write_ms,
            neo4j_write_ms,
            mongo_write_ms,
            total_latency_ms
    ):

        query = """
            INSERT INTO event_metrics(
                event_id,
                received_at,
                validated_at,
                validation_ms,
                mysql_write_ms,
                neo4j_write_ms,
                mongo_write_ms,
                total_latency_ms
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            event_id,
            received_at,
            validated_at,
            validation_ms,
            mysql_write_ms,
            neo4j_write_ms,
            mongo_write_ms,
            total_latency_ms
        )

        self.cursor.execute(query, values)

        self.connection.commit()


    def delete_location(self, location_name):

        query = "DELETE FROM locations WHERE location_name = %s"

        self.cursor.execute(query, (location_name,))

        self.connection.commit()


    def delete_sensor(self, sensor_id):

        query = "DELETE FROM sensors WHERE sensor_id = %s"

        self.cursor.execute(query, (sensor_id,))

        self.connection.commit()
