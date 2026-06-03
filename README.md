# Real-Time Environmental Monitoring System

A real-time environmental monitoring platform built with Python using MQTT-based asynchronous communication and a multi-database architecture.

The system simulates concurrent environmental sensors publishing telemetry data such as temperature, humidity, and air quality. Sensor events are processed and distributed across MySQL, MongoDB, and Neo4j to demonstrate how multiple database paradigms can work together within one event-driven architecture.

---

# Features

* Real-time MQTT communication using Eclipse Mosquitto
* Concurrent sensor simulation using Python threading
* Controlled random walk sensor value generation
* MySQL integration for structured relational analytics
* MongoDB integration for raw JSON event storage
* Neo4j integration for graph-based relationship modeling
* Real-time alert detection and persistence
* Centralized analytics engine
* Environment variable management using `.env`
* System logging using `logger.py`
* Colorized terminal output using `colorama`
* Graceful shutdown handling
* Modular and scalable project architecture

---

# Technologies Used

* Python
* MQTT
* Eclipse Mosquitto
* MySQL
* MongoDB
* Neo4j
* Paho MQTT
* PyMongo
* Neo4j Python Driver
* MySQL Connector Python
* Colorama
* Python Dotenv

---

# System Architecture

```text
Sensors
   ↓
MQTT Publisher
   ↓
MQTT Broker (Mosquitto)
   ↓
MQTT Subscriber
   ↓
-----------------------------------
| MySQL | MongoDB | Neo4j |
-----------------------------------
   ↓
Analytics Engine
```

---

# Database Roles

## MySQL

Used for:

* Structured relational storage
* Readings
* Alerts
* Sensor metadata
* Analytics queries

## MongoDB

Used for:

* Raw sensor event storage
* JSON document persistence
* Event archival

## Neo4j

Used for:

* Relationship modeling
* Sensor-location mapping
* Metric relationships
* Room connectivity visualization

---

# Analytics Features

The analytics engine supports:

1. Latest Sensor Readings
2. Average Temperature Per Room
3. Environmental Alerts
4. Raw MongoDB Events
5. Sensor Network Visualization
6. Room Connectivity Network
7. System Statistics

---

# Project Structure

```text
environment-monitoring-system/
│
├── analytics/
├── config/
├── database/
├── logs/
├── publisher/
├── subscriber/
├── tests/
│
├
├── requirements.txt
├── README.md
```

---

# How To Run

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Start Mosquitto Broker

```bash
mosquitto
```

## 3. Run Subscriber

```bash
python -m subscriber.mqtt_subscriber
```

## 4. Run Publishers

```bash
python tests/run_publishers.py
```

## 5. Run Analytics Engine

```bash
python analytics/analytics_menu.py
```

---

# Example MQTT Topics

```text
building/lab_a/temperature
building/lab_a/humidity
building/server_room/air_quality
building/office_1/air_quality
```

---

# Example Sensor Event

```json
{
  "sensor_id": "S1",
  "sensor_type": "temperature",
  "location": "Lab A",
  "value": 28.5,
  "unit": "C",
  "timestamp": "2026-06-03T10:42:10"
}
```

---

# Future Improvements

* Web dashboard
* Docker deployment
* Machine learning anomaly detection
* Cloud integration
* Real sensor hardware support

---

# Author

Eyasu Belete Abebe 

Real-Time Environmental Monitoring System
