from pymongo import MongoClient
from config.logger import logger

from colorama import Fore, init
init(autoreset=True)

class MongoDBHandler:

    def __init__(self, uri):

        self.client = MongoClient(uri)

        self.db = self.client["environment_monitoring"]

        self.collection = self.db["sensor_events"]

        logger.info(f"{Fore.GREEN}Connected to MongoDB{Fore.RESET}")

    def insert_event(self, event):

        self.collection.insert_one(event)

        logger.info(f"{Fore.GREEN}Inserted into MongoDB{Fore.RESET}")

    