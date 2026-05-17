import mysql.connector

class MySQLHandler:

    def __init__(self, host, user, password, database):

        self.connection = mysql.connector.connect(
            host = host,
            user = user,
            password = password,
            database = database
        )

        self.cursor = self.connection.cursor()

        print("Connected to MySQL")


    def initialize_tables(self):

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS locations(
                location_id INT AUTO_INCREMENT PRIMARY KEY,
                location_name VARCHAR(100) UNIQUE,
                location_type VARCHAR(100)
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensors(
                sensor_id VARCHAR(50) PRIMARY KEY,
                sensor_type VARCHAR(50),
                unit VARCHAR(20),
                location_id INT,
                FOREIGN KEY (location_id)
                    REFERENCES locations(location_id)
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS readings(
                reading_id INT AUTO_INCREMENT PRIMARY KEY,
                sensor_id VARCHAR(50),
                value FLOAT,
                timestamp DATETIME,
                FOREIGN KEY (sensor_id)
                    REFERENCES sensors(sensor_id)
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts(
                alert_id INT AUTO_INCREMENT PRIMARY KEY,
                sensor_id VARCHAR(50),
                severity VARCHAR(20),
                message TEXT,
                timestamp DATETIME,
                FOREIGN KEY (sensor_id)
                    REFERENCES sensors(sensor_id)
            )
        """)

        self.connection.commit()

        print("MySQL tables initialized")


    def insert_location(self, location_name, location_type):

        query = """
            INSERT IGNORE INTO locations(
                location_name,
                location_type
            )
            VALUES (%s, %s)
        """

        values = (location_name, location_type)

        self.cursor.execute(query, values)

        self.connection.commit()


    def insert_sensor(
            self,
            sensor_id,
            sensor_type,
            unit,
            location_name
    ):

        #find locaiton id
        self.cursor.execute("""
            SELECT location_id
            FROM locations
            WHERE location_name = %s
        """, (location_name,))

        result = self.cursor.fetchone()

        if result is None:
            print(f"Location not found: {location_name}")
            return

        location_id = result[0]

        query = """
            INSERT IGNORE INTO sensors(
                sensor_id,
                sensor_type,
                unit,
                location_id
            )
            VALUES (%s, %s, %s, %s)
        """

        values = (sensor_id, sensor_type, unit, location_id)

        self.cursor.execute(query, values)

        self.connection.commit()


    def insert_readings(
            self,
            sensor_id,
            value,
            timestamp
    ):

        query = """
            INSERT INTO readings(
                sensor_id,
                value,
                timestamp
            )
            VALUES (%s, %s, %s)
        """

        values = (sensor_id, value, timestamp)

        self.cursor.execute(query, values)

        self.connection.commit()












