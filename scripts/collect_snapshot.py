import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import save_readings
from src.history import save_home_snapshot
from src.hmip_provider import HomematicProviderError, load_home, map_room_readings


DATABASE_PATH = PROJECT_ROOT / "data" / "heating_data.db"


def collect_once(snapshot_interval_minutes: int) -> tuple[int, int]:
    home = load_home()
    recorded_at = datetime.now(timezone.utc)
    room_readings = map_room_readings(home)
    save_readings(DATABASE_PATH, room_readings)
    snapshot_count = save_home_snapshot(
        DATABASE_PATH,
        home,
        recorded_at,
        min_interval_minutes=snapshot_interval_minutes,
    )
    return len(room_readings), snapshot_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive current Homematic IP data locally.")
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Repeat every N seconds. Omit to collect one snapshot and exit.",
    )
    parser.add_argument(
        "--snapshot-interval",
        type=int,
        default=30,
        help="Minimum minutes between full Homematic snapshots.",
    )
    arguments = parser.parse_args()

    while True:
        try:
            room_count, snapshot_count = collect_once(arguments.snapshot_interval)
            print(f"Collected {room_count} rooms and {snapshot_count} Homematic objects.")
        except HomematicProviderError as error:
            print(f"Collection failed: {error}")
            if arguments.interval <= 0:
                return 1
        except Exception as error:
            print(f"Collection failed: {type(error).__name__}: {error}")
            if arguments.interval <= 0:
                return 1

        if arguments.interval <= 0:
            return 0
        time.sleep(arguments.interval)


if __name__ == "__main__":
    raise SystemExit(main())
