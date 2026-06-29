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
* Neo4j integration for graph-based relationship modeling, kept automatically in sync with live sensor events
* Real-time alert detection and persistence, with defensive normalization so a stray typo/case mismatch in a sensor payload can't silently disable an alert
* Per-event pipeline performance metrics (validation/MySQL/MongoDB latency) for the dashboard's Performance page
* Centralized analytics engine
* Streamlit web dashboard (system overview, live readings, alerts, performance, analytics, manage)
* Containerized with Docker Compose (broker, three databases, publisher, subscriber, dashboard)
* Automated unit test suite (pytest) with CI on every push
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
* Streamlit
* pytest
* GitHub Actions

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
Analytics Engine / Dashboard
```

---

# Database Roles

## MySQL

Used for:

* Structured relational storage
* Readings
* Alerts
* Sensor metadata
* Pipeline performance metrics
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

The subscriber keeps the graph in sync automatically: every incoming event MERGEs the corresponding Sensor/Location/Metric nodes, and a small set of known room adjacencies is seeded on startup. No manual step is required for the dashboard's "Sensor network" / "Room network" views to populate.

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
├── dashboard/
├── database/
├── logs/
├── publisher/
├── subscriber/
├── tests/
├── .github/workflows/      # CI pipeline
│
├── docker-compose.yml
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
├── README.md
```

---

# How To Run

## Option A: Docker Compose (recommended)

```bash
docker compose up --build
```

This starts Mosquitto, MySQL, MongoDB, Neo4j, the subscriber, a publisher (simulated sensors), and the dashboard at `http://localhost:8501`. Tables and sample sensors/locations are seeded automatically on first start.

## Option B: Run Manually

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

# Testing

The project ships with an automated pytest suite covering sensor value generation/bounds, MQTT publish/subscribe handling, alert-threshold logic (including sensor-type normalization), and the MySQL/MongoDB/Neo4j handlers. All database and broker clients are mocked, so the suite runs without any live infrastructure.

```bash
pip install -r requirements-dev.txt
pytest -v
```

A GitHub Actions workflow (`.github/workflows/ci.yml`) runs this suite automatically on every push and pull request, across Python 3.11 and 3.12.

---

# Configuration & Security

Copy `.env.example` to `.env` (and `config/.env.example` to `config/.env` if running manually) and fill in real values. `.env` files are excluded from version control via `.gitignore` -- never commit real credentials.

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

* Machine learning anomaly detection
* Cloud integration
* Real sensor hardware support
* Per-service Dockerfiles (instead of installing dependencies on every container start)

---

# Author

Eyasu Belete Abebe

Real-Time Environmental Monitoring System
