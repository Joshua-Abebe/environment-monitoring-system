from database.neo4j_handler import Neo4jHandler
from config.settings import NEO4J_CONFIG

class Neo4jAnalytics:

    def __init__(self):

        self.neo4j_handler = Neo4jHandler(
            **NEO4J_CONFIG
        )

    def view_sensor_network(self):

        query = """
            MATCH (s:Sensor)-[:LOCATED_IN]->(l:Location)
            RETURN s.id, l.name
        """


        with self.neo4j_handler.driver.session(database="environmentMonitoring") as session:

            result_query1 = session.run(query)


            print("\n=======Sensor Network=======\n")

            for record in result_query1:
                print(f"{record['s.id']} --> {record['l.name']}")



    def view_room_network(self):

        query = """
            MATCH(r1:Location)-[:CONNECTED_TO]->(r2:Location)
            RETURN r1.name, r2.name
        """

        with self.neo4j_handler.driver.session(database="environmentMonitoring") as session:

            result_query1 = session.run(query)


            print("\n=======Room Network (Connected Rooms)=======\n")

            for record in result_query1:
                print(f"{record['r1.name']}--->{record['r2.name']}")