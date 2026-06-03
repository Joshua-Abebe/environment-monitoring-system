from analytics.mysql_analytics import MySQLAnalytics
from analytics.mongodb_analytics import MongoDBAnalytics
from analytics.neo4j_analytics import Neo4jAnalytics

mysql_analytics = MySQLAnalytics()
mongodb_analytics = MongoDBAnalytics()
neo4j_analytics = Neo4jAnalytics()

while True:

    print("\n=======Environmental Monitoring Analytics=========\n")

    print("1. View Latest Sensor Readings")
    print("2. Average Temperature Per Room")
    print("3. View Environmental Alerts")
    print("4. View Raw MongoDB Events")
    print("5. View Sensor Network")
    print("6. View Room Network")
    print("7. System Statistics")
    print("8. Exit")

    choice = input("\nEnter choice: ")

    if choice == "1":
        mysql_analytics.latest_readings()

    elif choice == "2":
        mysql_analytics.avg_temperature_per_room()

    elif choice == "3":
        mysql_analytics.view_alerts()

    elif choice == "4":
        mongodb_analytics.view_recent_events()

    elif choice == "5":
        neo4j_analytics.view_sensor_network()

    elif choice == "6":
        neo4j_analytics.view_room_network()

    elif choice == "7":
        mysql_analytics.total_readings()
        mysql_analytics.total_sensors()
        mysql_analytics.total_alerts()

    elif choice == "8":
        print("Exiting Analytics System")
        break

    else:
        print("Invalid Input, Please Try Again")

