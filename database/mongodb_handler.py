from pymongo import MongoClient

class MongoDBHandler:

    def __init__(self, uri):

        self.client = MongoClient(uri)

        self.db = self.client["environment_monitoring"]

        self.collection = self.db["sensor_events"]

        print("Connected to MongoDB")

    def insert_event(self, event):

        self.collection.insert_one(event)

        print("Inserted into MongoDB")

    