import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import mysql.connector
import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import MYSQL_CONFIG, MONGO_URI, NEO4J_CONFIG
from config.sensor_defaults import (
    SENSOR_TYPE_DEFAULTS,
    DEFAULT_MIN_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_INITIAL_VALUE,
    DEFAULT_INTERVAL_SECONDS,
)
from database.mongodb_handler import MongoDBHandler
from database.mysql_handler import MySQLHandler
from database.neo4j_handler import Neo4jHandler


st.set_page_config(
    page_title="Environment Monitoring",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
    h1, h2, h3 {letter-spacing: 0;}
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e8edf3;
        border-radius: 8px;
        padding: 16px 18px;
        box-shadow: 0 6px 18px rgba(21, 35, 55, 0.06);
    }
    div[data-testid="stMetric"] * {color: #172033 !important;}
    div[data-testid="stMetricLabel"] * {color: #58667a !important;}
    .severity-high {
        color: #9f1239;
        background: #ffe4e6;
        padding: 0.15rem 0.45rem;
        border-radius: 999px;
        font-weight: 700;
    }
    .severity-medium {
        color: #92400e;
        background: #fef3c7;
        padding: 0.15rem 0.45rem;
        border-radius: 999px;
        font-weight: 700;
    }
    .severity-low {
        color: #166534;
        background: #dcfce7;
        padding: 0.15rem 0.45rem;
        border-radius: 999px;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# The publisher/subscriber containers run on UTC clocks, so every stored
# timestamp is naive UTC. We convert to this timezone only when displaying
# values in the dashboard, never when writing to the databases.
DISPLAY_TZ = ZoneInfo("Europe/Rome")


def to_local(series):
    """Convert naive UTC timestamps to DISPLAY_TZ for on-screen display."""
    timestamps = pd.to_datetime(series)
    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize("UTC")
    return timestamps.dt.tz_convert(DISPLAY_TZ).dt.tz_localize(None)


def mysql_connection():
    return mysql.connector.connect(**MYSQL_CONFIG)


def read_mysql(query, params=None):
    connection = mysql_connection()
    try:
        return pd.read_sql(query, connection, params=params)
    finally:
        connection.close()


def execute_action(action):
    handler = MySQLHandler(**MYSQL_CONFIG)
    handler.initialize_tables()
    try:
        return action(handler)
    finally:
        handler.connection.close()


def ensure_mysql_tables():
    handler = MySQLHandler(**MYSQL_CONFIG)
    try:
        handler.initialize_tables()
    finally:
        handler.connection.close()


def rooms_df():
    return read_mysql(
        """
        SELECT location_id, location_name, location_type
        FROM locations
        ORDER BY location_name
        """
    )


def sensors_df():
    return read_mysql(
        """
        SELECT s.sensor_id, s.sensor_type, s.unit, l.location_name
        FROM sensors s
        JOIN locations l ON s.location_id = l.location_id
        ORDER BY s.sensor_id
        """
    )


def sensor_intervals_df():
    """Empirically observed publish interval per sensor, in seconds.

    This is derived from the actual gaps between each sensor's most recent
    readings -- not a static config value -- so it reflects whatever a
    sensor is really doing. A sensor with fewer than two readings (e.g.
    one just added via Manage with no publisher behind it yet) has no
    measurable gap and is simply absent from the result.
    """
    return read_mysql(
        """
        SELECT sensor_id, AVG(gap_seconds) AS avg_interval_seconds
        FROM (
            SELECT
                r.sensor_id,
                TIMESTAMPDIFF(
                    SECOND,
                    LAG(r.timestamp) OVER (PARTITION BY r.sensor_id ORDER BY r.timestamp),
                    r.timestamp
                ) AS gap_seconds,
                ROW_NUMBER() OVER (PARTITION BY r.sensor_id ORDER BY r.timestamp DESC) AS rn
            FROM readings r
        ) gaps
        WHERE rn <= 6 AND gap_seconds IS NOT NULL
        GROUP BY sensor_id
        """
    )


def render_overview():
    st.subheader("System overview")

    counts = read_mysql(
        """
        SELECT
            (SELECT COUNT(*) FROM sensors) AS sensors,
            (SELECT COUNT(*) FROM locations) AS rooms,
            (SELECT COUNT(*) FROM readings WHERE DATE(timestamp) = CURDATE()) AS events_today,
            (SELECT COUNT(*) FROM alerts) AS alerts
        """
    ).iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sensors", int(counts["sensors"]))
    col2.metric("Rooms", int(counts["rooms"]))
    col3.metric("Events today", int(counts["events_today"]))
    col4.metric("Alerts", int(counts["alerts"]))


def render_live_readings():
    st.subheader("Live readings")

    latest = read_mysql(
        """
        SELECT s.sensor_id, s.sensor_type, s.unit, l.location_name, r.value, r.timestamp
        FROM readings r
        JOIN sensors s ON r.sensor_id = s.sensor_id
        JOIN locations l ON s.location_id = l.location_id
        JOIN (
            SELECT sensor_id, MAX(timestamp) AS max_timestamp
            FROM readings
            GROUP BY sensor_id
        ) latest ON latest.sensor_id = r.sensor_id AND latest.max_timestamp = r.timestamp
        ORDER BY l.location_name, s.sensor_type
        """
    )

    if latest.empty:
        st.info("No readings yet.")
    else:
        latest = latest.copy()
        latest["timestamp"] = to_local(latest["timestamp"])
        latest = latest.merge(sensor_intervals_df(), on="sensor_id", how="left")

        st.caption(
            "Each tile shows the single most recent reading per sensor (not an "
            "average). Times are shown in Europe/Rome local time. The label under "
            "each tile is the sensor id and its observed publish interval, measured "
            "from the gaps between its last few readings."
        )
        metric_cols = st.columns(min(4, len(latest)))
        for index, (_, row) in enumerate(latest.iterrows()):
            label = f'{row["location_name"]} - {row["sensor_type"]} (latest)'
            if pd.notna(row["avg_interval_seconds"]):
                sensor_caption = f'{row["sensor_id"]} - every ~{row["avg_interval_seconds"]:.0f}s'
            else:
                sensor_caption = f'{row["sensor_id"]} - interval unknown (too few readings)'
            metric_cols[index % len(metric_cols)].metric(
                label,
                f'{row["value"]:.2f} {row["unit"]}',
                sensor_caption,
            )
        st.dataframe(latest, use_container_width=True, hide_index=True)

    # Windowed PER SENSOR (not a single global LIMIT) so a sensor that
    # publishes less often -- or one that briefly stops publishing -- can't
    # get crowded out of the recent-history window by sensors that publish
    # more frequently. Each sensor keeps its own most recent rows.
    history = read_mysql(
        """
        SELECT timestamp, value, sensor_id, sensor_type, unit, location_name
        FROM (
            SELECT
                r.timestamp, r.value, s.sensor_id, s.sensor_type, s.unit, l.location_name,
                ROW_NUMBER() OVER (
                    PARTITION BY r.sensor_id ORDER BY r.timestamp DESC
                ) AS rn
            FROM readings r
            JOIN sensors s ON r.sensor_id = s.sensor_id
            JOIN locations l ON s.location_id = l.location_id
        ) ranked
        WHERE rn <= 50
        ORDER BY timestamp
        """
    )

    if not history.empty:
        history = history.copy()
        history["timestamp"] = to_local(history["timestamp"])

        st.markdown("#### Trends by sensor type")
        st.caption("Last 50 readings per sensor, so slower-publishing sensors still show up here.")
        sensor_types = sorted(history["sensor_type"].unique())
        type_tabs = st.tabs([t.replace("_", " ").title() for t in sensor_types])
        for tab, sensor_type in zip(type_tabs, sensor_types):
            with tab:
                subset = history[history["sensor_type"] == sensor_type].copy()
                unit = subset["unit"].iloc[0]
                subset["series"] = subset["location_name"]
                chart_data = subset.sort_values("timestamp").pivot_table(
                    index="timestamp",
                    columns="series",
                    values="value",
                    aggfunc="mean",
                )
                st.caption(f"Unit: {unit}")
                st.line_chart(chart_data, use_container_width=True)


def render_alerts():
    st.subheader("Alerts")

    with st.expander("What do HIGH and MEDIUM alerts mean?"):
        st.markdown(
            "Alerts are raised automatically by the subscriber as each reading "
            "comes in:\n\n"
            "- **HIGH** - temperature above **35 C**, or air quality above **80 AQI**.\n"
            "- **MEDIUM** - humidity above **70%**.\n\n"
            "Thresholds are defined in `subscriber/mqtt_subscriber.py` and checked "
            "on every reading."
        )

    alerts = read_mysql(
        """
        SELECT a.alert_id, a.sensor_id, l.location_name, s.sensor_type,
               a.severity, a.message, a.timestamp
        FROM alerts a
        LEFT JOIN sensors s ON a.sensor_id = s.sensor_id
        LEFT JOIN locations l ON s.location_id = l.location_id
        ORDER BY a.timestamp DESC
        LIMIT 100
        """
    )

    if alerts.empty:
        st.success("No alerts recorded.")
        return

    alerts = alerts.copy()
    alerts["timestamp"] = to_local(alerts["timestamp"])

    def severity_badge(value):
        css_class = {
            "HIGH": "severity-high",
            "MEDIUM": "severity-medium",
        }.get(str(value).upper(), "severity-low")
        return f'<span class="{css_class}">{value}</span>'

    styled = alerts.copy()
    styled["severity"] = styled["severity"].apply(severity_badge)
    st.write(styled.to_html(escape=False, index=False), unsafe_allow_html=True)


def render_performance():
    st.subheader("Performance")
    ensure_mysql_tables()

    st.markdown("### Write performance")
    st.caption(
        "Per-event latency recorded by the subscriber as it processes each MQTT "
        "message. Validation and Total are measured from the same start point "
        "(Total includes Validation, it isn't added on top of it). MySQL, "
        "Neo4j and MongoDB writes are each timed independently, around just "
        "that one write call."
    )

    metrics = read_mysql(
        """
        SELECT event_id, received_at, validated_at, validation_ms, mysql_write_ms,
               neo4j_write_ms, mongo_write_ms, total_latency_ms
        FROM event_metrics
        ORDER BY received_at DESC
        LIMIT 300
        """
    )

    if metrics.empty:
        st.info("No performance metrics yet.")
    else:
        metrics = metrics.copy()
        metrics["received_at"] = to_local(metrics["received_at"])
        metrics["validated_at"] = to_local(metrics["validated_at"])

        avg = metrics[
            ["validation_ms", "mysql_write_ms", "neo4j_write_ms", "mongo_write_ms", "total_latency_ms"]
        ].mean()
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Avg validation", f'{avg["validation_ms"]:.1f} ms')
        col2.metric("Avg MySQL write", f'{avg["mysql_write_ms"]:.1f} ms')
        col3.metric("Avg Neo4j write", f'{avg["neo4j_write_ms"]:.1f} ms')
        col4.metric("Avg MongoDB write", f'{avg["mongo_write_ms"]:.1f} ms')
        col5.metric("Avg total latency", f'{avg["total_latency_ms"]:.1f} ms')

        stage_chart = pd.DataFrame(
            {
                "Stage": ["Validation", "MySQL write", "Neo4j write", "MongoDB write", "Total"],
                "Latency ms": [
                    avg["validation_ms"],
                    avg["mysql_write_ms"],
                    avg["neo4j_write_ms"],
                    avg["mongo_write_ms"],
                    avg["total_latency_ms"],
                ],
            }
        ).set_index("Stage")
        st.bar_chart(stage_chart, use_container_width=True)

        latency_over_time = metrics.sort_values("received_at").set_index("received_at")[
            ["validation_ms", "mysql_write_ms", "neo4j_write_ms", "mongo_write_ms", "total_latency_ms"]
        ]
        st.line_chart(latency_over_time, use_container_width=True)
        st.dataframe(metrics, use_container_width=True, hide_index=True)

    st.markdown("### Read performance")
    st.caption(
        "Each connection below is opened and warmed up with a throwaway call "
        "first, then the real query is timed on its own. Without the warm-up, "
        "whichever database happens to need the heaviest one-time connection "
        "handshake looks artificially slow -- that's why Neo4j's BOLT "
        "handshake (a multi-message connect + auth exchange) used to make it "
        "look like the slowest database here even though it isn't."
    )

    read_benchmarks = []

    # MySQL: open one connection, warm it up, then time each query in
    # isolation. read_mysql() above opens a brand-new connection on every
    # call, which would otherwise bake connection-setup cost into every
    # single MySQL number and make the comparison uneven.
    mysql_conn = mysql_connection()
    try:
        pd.read_sql("SELECT 1", mysql_conn)  # warm-up, not timed

        mysql_queries = [
            (
                "MySQL: latest readings",
                """
                SELECT s.sensor_id, r.value, r.timestamp
                FROM readings r
                JOIN (
                    SELECT sensor_id, MAX(timestamp) AS max_timestamp
                    FROM readings
                    GROUP BY sensor_id
                ) latest ON latest.sensor_id = r.sensor_id AND latest.max_timestamp = r.timestamp
                JOIN sensors s ON r.sensor_id = s.sensor_id
                """,
            ),
            ("MySQL: alerts (100)", "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 100"),
            ("MySQL: event metrics (300)", "SELECT * FROM event_metrics ORDER BY received_at DESC LIMIT 300"),
        ]
        for label, query in mysql_queries:
            start = time.perf_counter()
            pd.read_sql(query, mysql_conn)
            read_benchmarks.append((label, (time.perf_counter() - start) * 1000))
    finally:
        mysql_conn.close()

    # MongoDB: pymongo's MongoClient connects lazily on first use, so a
    # throwaway find_one() pays that connection cost before the timer starts.
    mongo_handler = MongoDBHandler(MONGO_URI)
    try:
        mongo_handler.collection.find_one()  # warm-up, not timed

        start = time.perf_counter()
        list(mongo_handler.collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(10))
        read_benchmarks.append(("MongoDB: latest 10 events", (time.perf_counter() - start) * 1000))
    finally:
        mongo_handler.client.close()

    # Neo4j: GraphDatabase.driver() doesn't eagerly connect either -- the
    # actual BOLT handshake (TCP connect + protocol negotiation + HELLO/
    # auth) only happens on the first session.run(). A throwaway "RETURN 1"
    # pays that one-time cost up front so the timed query below measures
    # just the Cypher query itself.
    neo4j_handler = Neo4jHandler(**NEO4J_CONFIG)
    try:
        with neo4j_handler.driver.session(database="environmentmonitoring") as session:
            session.run("RETURN 1").consume()  # warm-up, not timed

            start = time.perf_counter()
            list(session.run(
                "MATCH (s:Sensor)-[:LOCATED_IN]->(l:Location) "
                "RETURN s.id AS sensor_id, l.name AS location LIMIT 50"
            ))
            read_benchmarks.append(("Neo4j: sensor network", (time.perf_counter() - start) * 1000))
    finally:
        neo4j_handler.close()

    bench_df = pd.DataFrame(read_benchmarks, columns=["Query", "Latency ms"])
    bench_cols = st.columns(len(bench_df))
    for col, (_, row) in zip(bench_cols, bench_df.iterrows()):
        col.metric(row["Query"], f'{row["Latency ms"]:.1f} ms')
    st.bar_chart(bench_df.set_index("Query"), use_container_width=True)


def render_analytics():
    st.subheader("Analytics")

    latest_tab, temp_tab, alerts_tab, mongo_tab, sensor_tab, room_tab, stats_tab = st.tabs(
        [
            "Latest readings",
            "Avg temperature",
            "Alerts",
            "Raw events",
            "Sensor network",
            "Room network",
            "Statistics",
        ]
    )

    with latest_tab:
        latest = read_mysql(
            """
            SELECT r.reading_id, r.sensor_id, s.sensor_type, l.location_name,
                   r.value, s.unit, r.timestamp
            FROM readings r
            LEFT JOIN sensors s ON r.sensor_id = s.sensor_id
            LEFT JOIN locations l ON s.location_id = l.location_id
            ORDER BY r.timestamp DESC
            LIMIT 10
            """
        )
        if latest.empty:
            st.info("No readings yet.")
        else:
            latest = latest.copy()
            latest["timestamp"] = to_local(latest["timestamp"])
            st.dataframe(latest, use_container_width=True, hide_index=True)

    with temp_tab:
        avg_temperature = read_mysql(
            """
            SELECT l.location_name, AVG(r.value) AS avg_temperature
            FROM readings r
            JOIN sensors s ON r.sensor_id = s.sensor_id
            JOIN locations l ON s.location_id = l.location_id
            WHERE s.sensor_type = 'temperature'
            GROUP BY l.location_name
            ORDER BY l.location_name
            """
        )
        if avg_temperature.empty:
            st.info("No temperature readings yet.")
        else:
            st.bar_chart(avg_temperature.set_index("location_name"), use_container_width=True)
            st.dataframe(avg_temperature.round(2), use_container_width=True, hide_index=True)

    with alerts_tab:
        alerts = read_mysql(
            """
            SELECT alert_id, sensor_id, severity, message, timestamp
            FROM alerts
            ORDER BY timestamp DESC
            LIMIT 50
            """
        )
        if alerts.empty:
            st.success("No alerts recorded.")
        else:
            alerts = alerts.copy()
            alerts["timestamp"] = to_local(alerts["timestamp"])
            st.dataframe(alerts, use_container_width=True, hide_index=True)

    with mongo_tab:
        mongo_handler = MongoDBHandler(MONGO_URI)
        try:
            events = list(
                mongo_handler.collection.find(
                    {},
                    {"_id": 0},
                ).sort("timestamp", -1).limit(10)
            )
        finally:
            mongo_handler.client.close()
        if not events:
            st.info("No MongoDB events yet.")
        else:
            events_df = pd.DataFrame(events)
            if "timestamp" in events_df:
                events_df["timestamp"] = to_local(events_df["timestamp"])
            st.dataframe(events_df, use_container_width=True, hide_index=True)

    with sensor_tab:
        neo4j_handler = Neo4jHandler(**NEO4J_CONFIG)
        try:
            with neo4j_handler.driver.session(database="environmentmonitoring") as session:
                result = session.run(
                    """
                    MATCH (s:Sensor)-[:LOCATED_IN]->(l:Location)
                    MATCH (s)-[:MEASURES]->(m:Metric)
                    RETURN s.id AS sensor_id, l.name AS location, m.name AS metric
                    ORDER BY sensor_id
                    """
                )
                rows = [record.data() for record in result]
        finally:
            neo4j_handler.close()
        if not rows:
            st.info("No sensor graph relationships yet.")
        else:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with room_tab:
        neo4j_handler = Neo4jHandler(**NEO4J_CONFIG)
        try:
            with neo4j_handler.driver.session(database="environmentmonitoring") as session:
                result = session.run(
                    """
                    MATCH (r1:Location)-[:CONNECTED_TO]->(r2:Location)
                    RETURN r1.name AS from_room, r2.name AS to_room
                    ORDER BY from_room, to_room
                    """
                )
                rows = [record.data() for record in result]
        finally:
            neo4j_handler.close()
        if not rows:
            st.info("No room graph relationships yet.")
        else:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with stats_tab:
        render_overview()


def render_manage():
    st.subheader("Manage")

    room_data = rooms_df()
    sensor_data = sensors_df()
    room_names = room_data["location_name"].tolist()

    room_col, sensor_col = st.columns(2)

    with room_col:
        st.markdown("### Rooms")
        with st.form("add_room_form"):
            room_name = st.text_input("Room name")
            room_type = st.text_input("Room type")
            submitted = st.form_submit_button("Add room")
            if submitted and room_name and room_type:
                created = execute_action(lambda handler: handler.insert_location(room_name, room_type))
                if created:
                    st.success(f"Created room: {room_name} (type: {room_type})")
                else:
                    st.warning(f"Room '{room_name}' already exists -- no changes made")
                st.rerun()

        if not room_data.empty:
            delete_room = st.selectbox("Room to delete", room_names)
            confirm_room = st.checkbox("Confirm room delete")
            if st.button("Delete room", disabled=not confirm_room):
                #sensors in this room cascade-delete with it (FK ON DELETE
                #CASCADE) -- surface that in the message so it's not a
                #surprise when those sensors disappear from the list too
                room_sensor_ids = sensor_data.loc[
                    sensor_data["location_name"] == delete_room, "sensor_id"
                ].tolist()

                execute_action(lambda handler: handler.delete_location(delete_room))

                # Mirror the delete into Neo4j: removes the Location node
                # (and its CONNECTED_TO room relationships), plus every
                # Sensor node LOCATED_IN it and that sensor's MEASURES
                # relationship -- keeping the graph in sync with the
                # MySQL cascade-delete above.
                neo4j_handler = Neo4jHandler(**NEO4J_CONFIG)
                try:
                    neo4j_handler.delete_location(delete_room)
                finally:
                    neo4j_handler.close()

                if room_sensor_ids:
                    st.success(
                        f"Deleted room: {delete_room} "
                        f"(also removed {len(room_sensor_ids)} sensor(s) from MySQL and Neo4j: "
                        f"{', '.join(room_sensor_ids)})"
                    )
                else:
                    st.success(f"Deleted room: {delete_room} (MySQL + Neo4j)")
                st.rerun()

    with sensor_col:
        st.markdown("### Sensors")

        # Sensor type drives the Min/Max/Initial/Interval defaults below,
        # so it has to live outside the form: a form only reruns on
        # submit, and a widget inside one can't react to another widget's
        # change until then. Outside the form, picking a type updates the
        # simulation defaults on the very next render -- before Add sensor
        # is even clicked.
        type_options = list(SENSOR_TYPE_DEFAULTS.keys()) + ["Custom"]
        sensor_type_choice = st.selectbox("Sensor type", type_options, key="add_sensor_type_choice")
        if sensor_type_choice == "Custom":
            sensor_type = st.text_input("Custom sensor type name", key="add_sensor_custom_type")
            type_defaults = {}
        else:
            sensor_type = sensor_type_choice
            type_defaults = SENSOR_TYPE_DEFAULTS[sensor_type_choice]

        with st.form("add_sensor_form"):
            sensor_id = st.text_input("Sensor id")
            unit = st.text_input("Unit")
            sensor_room = st.selectbox("Room", room_names) if room_names else None

            # These four feed the publisher fleet's simulation, not just
            # the catalog row: tests/run_publishers.py builds its Sensor
            # objects straight from this table (see get_all_sensors()), so
            # whatever's saved here is what the simulated readings will
            # actually look like once the publisher restarts. Defaults
            # come from the sensor-type preset picked above
            # (config/sensor_defaults.py), so e.g. a temperature sensor
            # doesn't default to a 0-100 range that would constantly trip
            # the >35C alert -- they're still editable per-sensor though.
            st.caption(
                f"Simulation settings for '{sensor_type or '...'}' "
                "-- used by the publisher to generate this sensor's readings."
            )
            min_col, max_col = st.columns(2)
            min_value = min_col.number_input(
                "Min value", value=float(type_defaults.get("min_value", DEFAULT_MIN_VALUE)), step=1.0
            )
            max_value = max_col.number_input(
                "Max value", value=float(type_defaults.get("max_value", DEFAULT_MAX_VALUE)), step=1.0
            )
            initial_col, interval_col = st.columns(2)
            initial_value = initial_col.number_input(
                "Initial value", value=float(type_defaults.get("initial_value", DEFAULT_INITIAL_VALUE)), step=1.0
            )
            interval_seconds = interval_col.number_input(
                "Publish interval (seconds)",
                value=int(type_defaults.get("interval_seconds", DEFAULT_INTERVAL_SECONDS)),
                min_value=1,
                step=1,
            )

            submitted = st.form_submit_button("Add sensor")
            if submitted and sensor_id and sensor_type and unit and sensor_room:
                if min_value >= max_value:
                    st.warning("Min value must be less than max value -- sensor not created")
                else:
                    created = execute_action(
                        lambda handler: handler.insert_sensor(
                            sensor_id,
                            sensor_type,
                            unit,
                            sensor_room,
                            min_value=min_value,
                            max_value=max_value,
                            initial_value=initial_value,
                            interval_seconds=int(interval_seconds),
                        )
                    )
                    if created:
                        st.success(
                            f"Created sensor: {sensor_id} ({sensor_type}, {unit}) -> {sensor_room}. "
                            f"It will start publishing simulated readings the next time the publisher "
                            f"container restarts."
                        )
                    else:
                        st.warning(f"Sensor '{sensor_id}' was not created (id already exists or room no longer exists)")
                    st.rerun()

        if not sensor_data.empty:
            delete_sensor = st.selectbox("Sensor to delete", sensor_data["sensor_id"].tolist())
            confirm_sensor = st.checkbox("Confirm sensor delete")
            if st.button("Delete sensor", disabled=not confirm_sensor):
                deleted_row = sensor_data.loc[sensor_data["sensor_id"] == delete_sensor].iloc[0]

                execute_action(lambda handler: handler.delete_sensor(delete_sensor))

                # Mirror the delete into Neo4j: removes the Sensor node
                # plus its LOCATED_IN and MEASURES relationships, keeping
                # the graph in sync with the MySQL delete above.
                neo4j_handler = Neo4jHandler(**NEO4J_CONFIG)
                try:
                    neo4j_handler.delete_sensor(delete_sensor)
                finally:
                    neo4j_handler.close()

                st.success(
                    f"Deleted sensor: {delete_sensor} "
                    f"({deleted_row['sensor_type']}, {deleted_row['unit']}) from {deleted_row['location_name']} "
                    f"(MySQL + Neo4j)"
                )
                st.rerun()

    st.markdown("### Relationships")
    if room_names:
        st.markdown("#### Sensor graph links")
        st.caption("Pick a sensor, then the location and measurement type to link it to in Neo4j.")
        sensor_options = sensor_data["sensor_id"].tolist()
        if sensor_options:
            selected_sensor = st.selectbox("Sensor", sensor_options, key="graph_link_sensor")
            sensor_row = sensor_data[sensor_data["sensor_id"] == selected_sensor].iloc[0]

            metric_options = sorted(set(sensor_data["sensor_type"].tolist()) | {sensor_row["sensor_type"]})
            default_location_index = (
                room_names.index(sensor_row["location_name"])
                if sensor_row["location_name"] in room_names
                else 0
            )
            default_metric_index = metric_options.index(sensor_row["sensor_type"])

            with st.form("create_sensor_graph_form"):
                selected_location = st.selectbox("Location", room_names, index=default_location_index)
                selected_metric = st.selectbox("Measurement (metric)", metric_options, index=default_metric_index)
                submitted = st.form_submit_button("Create LOCATED_IN and MEASURES")
                if submitted:
                    neo4j_handler = Neo4jHandler(**NEO4J_CONFIG)
                    try:
                        neo4j_handler.create_sensor_relationships(
                            sensor_id=selected_sensor,
                            sensor_type=selected_metric,
                            location=selected_location,
                        )
                    finally:
                        neo4j_handler.close()
                    st.success(
                        f"Created graph links: {selected_sensor} -[LOCATED_IN]-> {selected_location}, "
                        f"{selected_sensor} -[MEASURES]-> {selected_metric}"
                    )

    if len(room_names) < 2:
        st.info("Add at least two rooms to manage room relationships.")
        return

    rel_col1, rel_col2 = st.columns(2)
    with rel_col1:
        with st.form("create_relationship_form"):
            room1 = st.selectbox("From room", room_names, key="create_room1")
            room2 = st.selectbox("To room", room_names, index=1, key="create_room2")
            submitted = st.form_submit_button("Create relationship")
            if submitted and room1 != room2:
                neo4j_handler = Neo4jHandler(**NEO4J_CONFIG)
                try:
                    neo4j_handler.connect_rooms(room1, room2)
                finally:
                    neo4j_handler.close()
                st.success(f"Connected {room1} to {room2}")

    with rel_col2:
        with st.form("delete_relationship_form"):
            room1 = st.selectbox("From room", room_names, key="delete_room1")
            room2 = st.selectbox("To room", room_names, index=1, key="delete_room2")
            confirm_rel = st.checkbox("Confirm relationship delete")
            submitted = st.form_submit_button("Delete relationship")
            if submitted and confirm_rel and room1 != room2:
                neo4j_handler = Neo4jHandler(**NEO4J_CONFIG)
                try:
                    neo4j_handler.delete_room_relationship(room1, room2)
                finally:
                    neo4j_handler.close()
                st.success(f"Deleted connection from {room1} to {room2}")


st.title("Environment Monitoring System")

if st.sidebar.button("Refresh data"):
    st.rerun()

page = st.sidebar.radio(
    "Dashboard",
    ["System overview", "Live readings", "Alerts", "Performance", "Analytics", "Manage"],
)

try:
    if page == "System overview":
        render_overview()
    elif page == "Live readings":
        render_live_readings()
    elif page == "Alerts":
        render_alerts()
    elif page == "Performance":
        render_performance()
    elif page == "Analytics":
        render_analytics()
    else:
        render_manage()
except Exception as exc:
    st.error(f"Dashboard data source error: {exc}")
