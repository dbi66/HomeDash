import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATABASE_PATH, HOMEDASH_COLLECTOR_INTERVAL, HOMEDASH_PROVIDER_TIMEOUT_SECONDS
from src.database import finish_collection_run, save_readings, start_collection_run
from src.history import save_home_snapshot
from src.hmip_provider import HomematicProviderError, load_home, map_room_readings
from src.retry import retry_call


def collect_once(snapshot_interval_minutes: int) -> tuple[int, int]:
    home = retry_call(load_home, timeout_seconds=HOMEDASH_PROVIDER_TIMEOUT_SECONDS)
    recorded_at = datetime.now(timezone.utc)
    room_readings = map_room_readings(home)
    if not room_readings:
        raise RuntimeError("No room readings returned")
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

    if arguments.interval == 0 and "HOMEDASH_COLLECTOR_INTERVAL" in os.environ:
        arguments.interval = HOMEDASH_COLLECTOR_INTERVAL

    next_run = time.monotonic()
    while True:
        started = datetime.now(timezone.utc)
        run_id = start_collection_run(DATABASE_PATH, "homematic", started.isoformat())
        try:
            room_count, snapshot_count = collect_once(arguments.snapshot_interval)
            finished = datetime.now(timezone.utc)
            finish_collection_run(
                DATABASE_PATH,
                run_id,
                finished_at=finished.isoformat(),
                status="success",
                record_count=room_count,
                duration_ms=int((finished - started).total_seconds() * 1000),
            )
            print(f"Collected {room_count} rooms and {snapshot_count} Homematic objects.")
        except HomematicProviderError as error:
            finished = datetime.now(timezone.utc)
            finish_collection_run(
                DATABASE_PATH,
                run_id,
                finished_at=finished.isoformat(),
                status="error",
                duration_ms=int((finished - started).total_seconds() * 1000),
                error=str(error),
            )
            print(f"Collection failed: {error}")
            if arguments.interval <= 0:
                return 1
        except Exception as error:
            finished = datetime.now(timezone.utc)
            finish_collection_run(
                DATABASE_PATH,
                run_id,
                finished_at=finished.isoformat(),
                status="error",
                duration_ms=int((finished - started).total_seconds() * 1000),
                error=f"{type(error).__name__}: {error}",
            )
            print(f"Collection failed: {type(error).__name__}: {error}")
            if arguments.interval <= 0:
                return 1

        if arguments.interval <= 0:
            return 0
        next_run += arguments.interval
        delay = next_run - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            next_run = time.monotonic()


if __name__ == "__main__":
    raise SystemExit(main())
