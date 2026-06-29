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

        # The value the sensor naturally idles around. A pure bounded
        # random walk (old behaviour) drifts and then lingers near
        # whichever edge it last wandered to, so it spends a large
        # fraction of its time sitting inside the alert zone -- that's
        # why alerts were firing almost constantly. Mean-reverting back
        # toward this point keeps day-to-day readings clustered near a
        # realistic "normal" operating value instead.
        self.normal_value = initial_value

        self.interval = interval

        # How strongly each step pulls current_value back toward
        # normal_value. 0.15 means ~15% of the gap is closed per
        # reading -- enough to keep the walk tight without making it
        # feel rigid/robotic.
        self.reversion_strength = 0.15

        # Probability that any given reading is a rare "anomaly" event
        # (a spike/dip large enough to occasionally cross an alert
        # threshold) rather than ordinary noise. Tuned empirically so
        # the full 6-sensor seed set produces on the order of a
        # handful of alert-worthy excursions per day -- occasional,
        # not constant, not silent either.
        self.anomaly_probability = 0.001


    def generate_values(self):

        """Mean-reverting random walk with rare anomaly events.

        Most readings are small noise around normal_value (the walk
        pulls itself back home each step). Occasionally -- on average
        about once every ~1000 readings per sensor -- an anomaly event
        nudges the value toward one of the bounds, which is what lets
        it occasionally cross into alert territory. This keeps alerts
        believable: they happen, but they're the exception, not the
        rule.
        """
        pull = (self.normal_value - self.current_value) * self.reversion_strength
        noise = random.uniform(-0.5, 0.5)

        anomaly = 0
        if random.random() < self.anomaly_probability:
            # Biased toward the high side since every alert threshold
            # in this system (temperature/humidity/air quality) is an
            # "above X" condition -- occasional spikes are what should
            # be able to trigger an alert, not dips.
            extreme = self.max_value if random.random() < 0.7 else self.min_value
            anomaly = (extreme - self.current_value) * random.uniform(0.4, 0.75)

        self.current_value += pull + noise + anomaly

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
