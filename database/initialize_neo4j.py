from database.neo4j_handler import Neo4jHandler

neo4j_handler = Neo4jHandler(
    uri="neo4j://127.0.0.1:7687",
    user="neo4j",
    password="projects5555"
)

neo4j_handler.create_sensor_relationships(
    sensor_id="s1",
    sensor_type="temperature",
    location="Lab A"
)

neo4j_handler.create_sensor_relationships(
    sensor_id="s2",
    sensor_type="humidity",
    location="Lab A"
)

neo4j_handler.create_sensor_relationships(
    sensor_id="s3",
    sensor_type="air_quality",
    location="Server Room"
)

neo4j_handler.close()