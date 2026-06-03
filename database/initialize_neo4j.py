from database.neo4j_handler import Neo4jHandler
from config.settings import NEO4J_CONFIG

neo4j_handler = Neo4jHandler(
    **NEO4J_CONFIG
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

neo4j_handler.create_sensor_relationships(
    sensor_id="s4",
    sensor_type="temprature",
    location="Lab B"
)

neo4j_handler.create_sensor_relationships(
    sensor_id="s5",
    sensor_type="humidity",
    location="Lab B"
)

neo4j_handler.create_sensor_relationships(
    sensor_id="s6",
    sensor_type="air_quality",
    location="Office 1"
)


neo4j_handler.connect_rooms(
    "Lab A",
    "Server Room"
)

neo4j_handler.connect_rooms(
    "Lab B",
    "Office 1"
)


neo4j_handler.close()