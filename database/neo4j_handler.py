from neo4j import GraphDatabase
from config.logger import logger

from colorama import Fore, init
init(autoreset=True)

class Neo4jHandler:

    def __init__(self, uri, user, password):

        self.driver = GraphDatabase.driver(
            uri,
            auth=(user, password)
        )

        logger.info("Connected to Neo4j")


    def close(self):

        self.driver.close()


    def create_sensor_relationships(
            self,
            sensor_id,
            sensor_type,
            location
    ):

        query = """
            MERGE (s:Sensor {id: $sensor_id})
            
            MERGE (l:Location {name: $location})
            
            MERGE (m:Metric {name: $sensor_type})
            
            MERGE (s)-[:LOCATED_IN]->(l)
            
            MERGE (s)-[:MEASURES]->(m)
        """

        with self.driver.session(database="environmentmonitoring") as session:

            session.run(
                query,
                sensor_id=sensor_id,
                sensor_type=sensor_type,
                location=location
            )

        logger.info(f"{Fore.GREEN}Relationship created for {sensor_id}{Fore.RESET}")



    def connect_rooms(self, room1, room2):

        # MERGE (not MATCH) the Location nodes: this must work even if no
        # Sensor has been linked to either room yet. The subscriber seeds
        # room connections once at startup, before any MQTT event has run
        # create_sensor_relationships, so a MATCH-only query would silently
        # find nothing and never create the relationship.
        query = """
            MERGE (r1:Location {name: $room1})
            
            MERGE (r2:Location {name: $room2})
            
            MERGE (r1)-[:CONNECTED_TO]->(r2)
        """

        with self.driver.session(database="environmentmonitoring") as session:

            session.run(
                query,
                room1=room1,
                room2=room2
            )

        logger.info(f"{Fore.GREEN}Room connection successfully created for {room1} and {room2}{Fore.RESET}")


    def delete_room_relationship(self, room1, room2):

        query = """
            MATCH (r1:Location {name: $room1})-[rel:CONNECTED_TO]->(r2:Location {name: $room2})

            DELETE rel
        """

        with self.driver.session(database="environmentmonitoring") as session:

            session.run(
                query,
                room1=room1,
                room2=room2
            )

        logger.info(f"{Fore.GREEN}Room connection deleted for {room1} and {room2}{Fore.RESET}")


    def delete_sensor(self, sensor_id):

        # DETACH DELETE removes the Sensor node together with every
        # relationship attached to it (LOCATED_IN -> Location,
        # MEASURES -> Metric), mirroring the MySQL-side sensor delete.
        query = """
            MATCH (s:Sensor {id: $sensor_id})

            DETACH DELETE s
        """

        with self.driver.session(database="environmentmonitoring") as session:

            session.run(
                query,
                sensor_id=sensor_id
            )

        logger.info(f"{Fore.GREEN}Sensor node and relationships deleted for {sensor_id}{Fore.RESET}")


    def delete_location(self, location_name):

        # OPTIONAL MATCH so a Location with no sensors yet still gets
        # deleted. DETACH DELETE on both s and l removes: every Sensor
        # node LOCATED_IN this location (and in turn its MEASURES
        # relationship), the Location node itself, and any CONNECTED_TO
        # relationships the location has with other rooms.
        query = """
            MATCH (l:Location {name: $location_name})

            OPTIONAL MATCH (s:Sensor)-[:LOCATED_IN]->(l)

            DETACH DELETE s, l
        """

        with self.driver.session(database="environmentmonitoring") as session:

            session.run(
                query,
                location_name=location_name
            )

        logger.info(f"{Fore.GREEN}Location, its sensors and relationships deleted for {location_name}{Fore.RESET}")
