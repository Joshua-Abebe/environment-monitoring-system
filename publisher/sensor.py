import random
from datetime import datetime

class Sensor:

    def __init__(
            self,
            sensor_id,
            sensor_type,
            location,
            unit,
            min_value,
            max_value,
            initial_value,
            interval
    ):

        self.sensor_id = sensor_id
        self.sensor_type = sensor_type
        self.location = location
        self.unit = unit

        self.min_value = min_value
        self.max_value = max_value

        self.current_value = initial_value

        self.interval = interval


    def generate_values(self):

        """controlled random walk, small fluctuation"""
        change = random.uniform(-0.5, 0.5)
        self.current_value += change


        #preventing out of bounds values
        self.current_value = max(self.min_value, self.current_value)
        self.current_value = min(self.max_value, self.current_value)

        return round(self.current_value, 2)

    def create_event(self):

        value = self.generate_values()

        event = {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "location": self.location,
            "value": value,
            "unit": self.unit,
            "timestamp": datetime.now().isoformat()
        }

        return event