import json
import time
import uuid
from datetime import datetime

import paho.mqtt.client as mqtt

from colorama import Fore, init
init(autoreset=True)

from config.settings import MYSQL_CONFIG
from config.settings import MQTT_CONFIG
from config.settings import MONGO_URI
from config.settings import NEO4J_CONFIG
from config.logger import logger
from database.mysql_handler import MySQLHandler
from database.mongodb_handler import MongoDBHandler
from database.neo4j_handler import Neo4jHandler

#known room adjacencies, used to seed the Neo4j "Room network" graph
ROOM_CONNECTIONS = [
    ("Lab A", "Server Room"),
    ("Lab B", "Office 1"),
]


class MQTTSubscriber:

    def __init__(self, broker, port):

        self.broker = broker
        self.port = port

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        #connect to MySQL DB
        self.mysql_handler = MySQLHandler(
            **MYSQL_CONFIG
        )
        #connect to MongoDB
        self.mongodb_handler = MongoDBHandler(MONGO_URI)

        #connect to Neo4j (non-fatal if unavailable -- the rest of the
        #pipeline should keep working even if the graph database is down)
        try:
            self.neo4j_handler = Neo4jHandler(**NEO4J_CONFIG)
            self._seed_room_connections()
        except Exception:
            self.neo4j_handler = None
            logger.exception(f"{Fore.RED}Failed to connect to Neo4j, graph features disabled{Fore.RESET}")

        #Tracks whether each sensor_id is currently "in alarm" so alerts
        #are edge-triggered: one alert per excursion above threshold,
        #not one per reading for as long as the excursion lasts. Without
        #this, a single real anomaly that takes a few readings to settle
        #back down would still spam one alert row per reading.
        self.active_alerts = {}


    def _seed_room_connections(self):
        """Idempotently link known rooms so the Room network analytics
        tab has data without requiring a manual Manage-page click."""

        for room1, room2 in ROOM_CONNECTIONS:
            try:
                self.neo4j_handler.connect_rooms(room1, room2)
            except Exception:
                logger.exception(f"{Fore.RED}Failed to connect rooms {room1} <-> {room2}{Fore.RESET}")


    def on_connect(self, client, userdata, flags, reasonCode, properties):

        logger.info(f"{Fore.GREEN}Connected to MQTT broker at {self.broker}:{self.port}{Fore.RESET}")

        self.client.subscribe("building/#")

        logger.info(f"{Fore.YELLOW}Subscribed to topic building/#{Fore.RESET}")


    def validate_event(self, event):

        required_fields = [
            "sensor_id",
            "sensor_type",
            "location",
            "unit",
            "value",
            "timestamp"
        ]

        for field in required_fields:

            if field not in event:
                return False
        return True


    def on_message(self, client, userdata, msg):

        # Timing model for the metrics recorded below (see the Performance
        # page's "Write performance" section):
        #   - validation_ms and total_latency_ms are CUMULATIVE -- both are
        #     measured from this same `start` reference, so total_latency_ms
        #     already includes validation_ms (and every stage after it).
        #     It is not "validation + mysql + neo4j + mongo" added on top.
        #   - mysql_write_ms, neo4j_write_ms and mongo_write_ms are each
        #     INDEPENDENT, self-contained timers: every one starts its own
        #     clock right before that single write call and stops right
        #     after, so they measure only that stage's own cost and are not
        #     nested inside one another.
        received_at = datetime.now()
        start = time.perf_counter()
        event_id = str(uuid.uuid4())

        try:
            payload = msg.payload.decode()

            event = json.loads(payload)

            logger.info(f"Recieved event: {event} | Topic: {msg.topic}")


            if not self.validate_event(event):

                logger.warning(f"{Fore.RED}Received invalid event, missing required fields{Fore.RESET}")
                logger.error(f"Invalid event: {event}")

                return

            validated_at = datetime.now()
            validation_ms = (time.perf_counter() - start) * 1000

            #normalize sensor_type so a stray typo/space/case mismatch in a
            #publisher can't silently break alert matching downstream
            sensor_type_normalized = str(event.get("sensor_type", "")).strip().lower().replace(" ", "_")

            #normalize the incoming ISO timestamp into a real datetime
            #so MySQL always receives a consistent value
            try:
                event_timestamp = datetime.fromisoformat(event["timestamp"])
            except (TypeError, ValueError):
                event_timestamp = received_at

            mysql_start = time.perf_counter()

            self.mysql_handler.insert_readings(
                sensor_id=event["sensor_id"],
                value=event["value"],
                timestamp=event_timestamp
            )

            mysql_write_ms = (time.perf_counter() - mysql_start) * 1000

            logger.info(f"{Fore.GREEN}Inserted into MySQL{Fore.RESET}")

            #Keep the Neo4j graph in sync with whatever sensors are
            #actually publishing, so the Sensor network analytics tab
            #populates automatically (no manual Manage-page step needed).
            #MERGE-based, so this is safe/cheap to run on every event.
            #Timed independently (like mysql_write_ms/mongo_write_ms) so its
            #cost shows up on the Performance page instead of disappearing
            #into total_latency_ms with no per-stage visibility.
            neo4j_write_ms = 0.0
            if self.neo4j_handler is not None:
                try:
                    neo4j_start = time.perf_counter()

                    self.neo4j_handler.create_sensor_relationships(
                        sensor_id=event["sensor_id"],
                        sensor_type=sensor_type_normalized,
                        location=event["location"]
                    )

                    neo4j_write_ms = (time.perf_counter() - neo4j_start) * 1000
                except Exception:
                    logger.exception(f"{Fore.RED}Failed to update Neo4j graph for {event['sensor_id']}{Fore.RESET}")

            #Alert logic
            #Normalize sensor_type defensively (trim whitespace, lowercase,
            #collapse spaces to underscores) so a stray typo in a publisher
            #("air quality" instead of "air_quality") can't silently make
            #alerts stop firing.
            value = event["value"]
            sensor_id = event["sensor_id"]

            severity = None
            message = None

            if sensor_type_normalized == "temperature" and value > 35:
                severity = "HIGH"
                message = "HIGH Temperature Detected"
            elif sensor_type_normalized == "humidity" and value > 70:
                severity = "MEDIUM"
                message = "HIGH Humidity Detected"
            elif sensor_type_normalized == "air_quality" and value > 80:
                severity = "HIGH"
                message = "POOR Air Quality Detected"

            is_alarm_condition = severity is not None
            was_already_alarming = self.active_alerts.get(sensor_id, False)

            #Edge-triggered: only insert a new alert row the moment a
            #sensor crosses INTO an alarm condition. While it stays over
            #threshold on subsequent readings we don't keep re-inserting
            #-- that would turn one real excursion into dozens of
            #duplicate alert rows. Once it drops back under threshold,
            #the state resets so the next excursion can alert again.
            if is_alarm_condition and not was_already_alarming:
                logger.warning(Fore.RED + f"{sensor_type_normalized.upper()} ALERT" + Fore.RESET)

                self.mysql_handler.insert_alert(
                    sensor_id=sensor_id,
                    severity=severity,
                    message=message,
                    timestamp=event_timestamp
                )

            self.active_alerts[sensor_id] = is_alarm_condition

            #Insert raw event to MongoDB. Isolated in its own try/except,
            #mirroring the Neo4j block above, so a MongoDB outage can't
            #silently take down the rest of the pipeline. Without this,
            #a Mongo failure would be caught by the broad except Exception
            #at the bottom of this method, which would also skip
            #insert_event_metrics below -- meaning MySQL/Neo4j writes keep
            #succeeding while MongoDB silently stops, with no record of the
            #failure anywhere and no metrics row for the event at all.
            mongo_write_ms = 0.0
            try:
                mongo_start = time.perf_counter()

                self.mongodb_handler.insert_event(event)

                mongo_write_ms = (time.perf_counter() - mongo_start) * 1000
            except Exception:
                logger.exception(f"{Fore.RED}Failed to insert event into MongoDB for {event['sensor_id']}{Fore.RESET}")

            total_latency_ms = (time.perf_counter() - start) * 1000

            #Track pipeline performance for the dashboard's Performance page
            self.mysql_handler.insert_event_metrics(
                event_id=event_id,
                received_at=received_at,
                validated_at=validated_at,
                validation_ms=validation_ms,
                mysql_write_ms=mysql_write_ms,
                neo4j_write_ms=neo4j_write_ms,
                mongo_write_ms=mongo_write_ms,
                total_latency_ms=total_latency_ms
            )

        except Exception:
            logger.exception(f"{Fore.RED}Failed to process message on topic {msg.topic}{Fore.RESET}")



    def start(self):

        self.client.connect(self.broker, self.port)

        self.client.loop_forever()


    def stop(self):
        """Best-effort graceful shutdown: disconnect the MQTT client and
        release every database connection opened in __init__. Each step
        is isolated in its own try/except so one failure (e.g. a handler
        that's already closed) can't stop the rest of the cleanup from
        running."""

        try:
            self.client.disconnect()
        except Exception:
            logger.exception(f"{Fore.RED}Failed to disconnect MQTT client{Fore.RESET}")

        try:
            self.mysql_handler.connection.close()
        except Exception:
            logger.exception(f"{Fore.RED}Failed to close MySQL connection{Fore.RESET}")

        try:
            self.mongodb_handler.client.close()
        except Exception:
            logger.exception(f"{Fore.RED}Failed to close MongoDB connection{Fore.RESET}")

        if self.neo4j_handler is not None:
            try:
                self.neo4j_handler.close()
            except Exception:
                logger.exception(f"{Fore.RED}Failed to close Neo4j connection{Fore.RESET}")

        logger.info(f"{Fore.YELLOW}Subscriber shut down cleanly{Fore.RESET}")



if __name__ == "__main__":
    subscriber = MQTTSubscriber(
        **MQTT_CONFIG
    )
    try:
        subscriber.start()

    except KeyboardInterrupt:

        print(f"{Fore.YELLOW}Subscriber shutting down......{Fore.RESET}")
        subscriber.stop()
