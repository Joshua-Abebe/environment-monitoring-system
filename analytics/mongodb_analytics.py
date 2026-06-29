from database.mongodb_handler import MongoDBHandler
from config.settings import MONGO_URI

class MongoDBAnalytics:

    def __init__(self):

        self.mongodb_handler = MongoDBHandler(MONGO_URI)


    def close(self):

        self.mongodb_handler.client.close()


    def view_recent_events(self):

        events = self.mongodb_handler.collection.find().sort(
            "timestamp",
            -1
        ).limit(10)

        print("\n======Raw MongoDB Events======\n")

        for event in events:
            print(event)
