from database.mongodb_handler import MongoDBHandler

mongodb_handler = MongoDBHandler(
    uri="mongodb://localhost:27017"
)

sample_event = {
    "sensor_id": "S1",
    "sensor_type": "temperature",
    "location": "Lab A",
    "unit": "C",
    "value": 28.5,
    "timestamp": "2026-05-18T15:30:00"
}

mongodb_handler.insert_event(sample_event)