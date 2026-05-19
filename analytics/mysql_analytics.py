from database.mysql_handler import MySQLHandler

class MySQLAnalytics:

    def __init__(self):

        self.mysql_handler = MySQLHandler(
            host="localhost",
            user="abc",
            password="projects5555",
            database="environment_monitoring"
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
            print(row)

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

        print("\n=====Environmental Alerts=====\n")

        for row in results:
            print(row)


    

