from neo4j import GraphDatabase

class Neo4jHandler:

    def __init__(self, uri, user, password):

        self.driver = GraphDatabase.driver(
            uri,
            auth=(user, password)
        )

        print("Connected to Neo4j")


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

        print(f"Relationship created for {sensor_id}")