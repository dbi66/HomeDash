from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATABASE_PATH, HOMEDASH_COLLECTOR_INTERVAL, HOMEDASH_VIESSMANN_INTERVAL
from src.database import get_latest_data_timestamps
from src.freshness import age_minutes


def check_database() -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise RuntimeError(f"database integrity check failed: {result}")


def check_freshness() -> None:
    timestamps = get_latest_data_timestamps(DATABASE_PATH)
    now = datetime.now(timezone.utc)
    limits = {
        "homematic": HOMEDASH_COLLECTOR_INTERVAL * 2 / 60,
        "viessmann": HOMEDASH_VIESSMANN_INTERVAL * 2 / 60,
    }
    for source, limit in limits.items():
        age = age_minutes(timestamps[source], now)
        if age is None or age > limit:
            raise RuntimeError(f"{source} data is stale: age={age} minutes, limit={limit}")


def check_http(url: str) -> None:
    with urlopen(url, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"dashboard returned HTTP {response.status}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HomeDash deployment health checks.")
    parser.add_argument("--url", default="http://127.0.0.1:8501/", help="Dashboard URL to probe.")
    arguments = parser.parse_args()
    check_database()
    check_freshness()
    check_http(arguments.url)
    print("HomeDash healthcheck: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
