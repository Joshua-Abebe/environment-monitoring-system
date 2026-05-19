from database.neo4j_handler import Neo4jHandler

class Neo4jAnalytics:

    def __init__(self):

        self.neo4j_handler = Neo4jHandler(
            uri="neo4j://127.0.0.1:7687",
            user="neo4j",
            password="projects5555"
        )

    def view_sensor_network(self):

        query = """
            MATCH (s:Sensor)-[:LOCATED_IN]->(l:Location)
            RETURN s.id, l.name
        """

        with self.neo4j_handler.driver.session(database="environmentMonitoring") as session:

            results = session.run(query)

            print("\n=======Sensor Network=======\n")

            for record in results:
                print(f"{record['s.id']} --> {record['l.name']}")