from database.mysql_handler import MySQLHandler
from config.settings import MYSQL_CONFIG

from colorama import Fore, init
init(autoreset=True)

class MySQLAnalytics:

    def __init__(self):

        self.mysql_handler = MySQLHandler(
            **MYSQL_CONFIG
        )


    def latest_readings(self):

        query = """
            SELECT *
            FROM readings
            ORDER BY timestamp DESC
            LIMIT 10
        """

        self.mysql_handler.cursor.execute(query)

        results = self.mysql_handler.cursor.fetchall()

        print("\n======Latest Sensor Readings=======\n")

        for row in results:
            print(f"""
                Sensor ID: {row[1]}
                Value: {row[2]}
                Timestamp: {row[3]}
                ---------------------------------------
            """)

    def avg_temperature_per_room(self):

        query = """
            SELECT l.location_name,
                   AVG(r.value) AS avg_temperature
                   
            FROM readings r 
            
            JOIN sensors s 
                ON r.sensor_id = s.sensor_id
                
            JOIN locations l 
                ON s.location_id = l.location_id
                
            WHERE s.sensor_type = "temperature"
                
            GROUP BY l.location_name
        """

        self.mysql_handler.cursor.execute(query)

        results = self.mysql_handler.cursor.fetchall()

        print("\n=====Average Temprature per Room======\n")

        for row in results:
            print(f"{row[0]}-->{round(row[1], 2)}")


    def view_alerts(self):

        query = """
            SELECT *
            FROM alerts
            ORDER BY timestamp DESC
        """

        self.mysql_handler.cursor.execute(query)

        results = self.mysql_handler.cursor.fetchall()

        print(f"\n{Fore.RED}=====Environmental Alerts=====\n{Fore.RESET}")

        for row in results:
            print(f"{Fore.RED}{row}{Fore.RESET}")


    def total_readings(self):

        query = """
            SELECT COUNT(*)
            FROM readings
        """

        self.mysql_handler.cursor.execute(query)

        result = self.mysql_handler.cursor.fetchone()

        print(f"\n{Fore.GREEN}Total Readings: {result}{Fore.RESET}")



    def total_sensors(self):

        query = """
                SELECT COUNT(*)
                FROM sensors 
                """

        self.mysql_handler.cursor.execute(query)

        result = self.mysql_handler.cursor.fetchone()

        print(f"\n{Fore.GREEN}Total Sensors: {result}{Fore.RESET}")


    def total_alerts(self):

        query = """
                SELECT COUNT(*)
                FROM alerts 
                """

        self.mysql_handler.cursor.execute(query)

        result = self.mysql_handler.cursor.fetchone()

        print(f"\n{Fore.RED}Total Alerts: {result}{Fore.RESET}")



    

