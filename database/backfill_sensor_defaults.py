"""One-time (but safe to re-run) backfill for sensors whose simulation
columns (min_value/max_value/initial_value/interval_seconds) are still
NULL -- e.g. s7, or any other sensor added through the dashboard's Manage
page before config/sensor_defaults.py's type-aware presets existed.

The publisher already works without this: load_sensors_from_catalog()
(tests/run_publishers.py) falls back to the same type-aware defaults in
memory at startup. This script just also writes those values back into
the `sensors` table, so the catalog itself shows real numbers instead of
NULL -- useful for visibility, and for whenever an "edit sensor" UI gets
added.

Run from inside the publisher (or any container with the repo mounted
and MySQL reachable), e.g.:

    docker compose exec publisher python -m database.backfill_sensor_defaults
"""

from database.mysql_handler import MySQLHandler
from config.settings import MYSQL_CONFIG
from config.logger import logger

from colorama import Fore, init
init(autoreset=True)


def main():
    handler = MySQLHandler(**MYSQL_CONFIG)
    try:
        handler.initialize_tables()
        updated = handler.backfill_sensor_simulation_defaults()
    finally:
        handler.connection.close()

    if updated:
        logger.info(
            f"{Fore.GREEN}Backfilled simulation defaults for: {', '.join(updated)}{Fore.RESET}"
        )
    else:
        logger.info(
            f"{Fore.GREEN}No sensors needed backfilling -- all simulation columns already set{Fore.RESET}"
        )


if __name__ == "__main__":
    main()
