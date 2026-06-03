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

        with self.driver.session(database="environmentMonitoring") as session:

            session.run(
                query,
                sensor_id=sensor_id,
                sensor_type=sensor_type,
                location=location
            )

        logger.info(f"{Fore.GREEN}Relationship created for {sensor_id}{Fore.RESET}")



    def connect_rooms(self, room1, room2):

        query = """
            MATCH (r1:Location {name: $room1})
            MATCH (r2:Location {name: $room2})
            
            MERGE (r1)-[:CONNECTED_TO]->(r2)
        """

        with self.driver.session(database="environmentMonitoring") as session:

            session.run(
                query,
                room1=room1,
                room2=room2
            )

        logger.info(f"{Fore.GREEN}Room connection successfully created for {room1} and {room2}{Fore.RESET}")