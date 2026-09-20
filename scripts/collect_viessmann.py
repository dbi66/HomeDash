import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATABASE_PATH, HOMEDASH_PROVIDER_TIMEOUT_SECONDS, HOMEDASH_VIESSMANN_INTERVAL
from src.database import finish_collection_run, save_viessmann_snapshots, start_collection_run
from src.viessmann_heatpump import read_heat_pumps
from src.viessmann_provider import ViessmannProviderError, load_client
from src.retry import retry_call


def collect_once() -> int:
    client = retry_call(load_client, timeout_seconds=HOMEDASH_PROVIDER_TIMEOUT_SECONDS)
    heat_pumps = retry_call(lambda: read_heat_pumps(client), timeout_seconds=HOMEDASH_PROVIDER_TIMEOUT_SECONDS)
    return save_viessmann_snapshots(
        DATABASE_PATH,
        [
            {
                "id": heat_pump.device_id,
                "model": heat_pump.model,
                "online": heat_pump.online,
                "features": heat_pump.features,
            }
            for heat_pump in heat_pumps
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive current Viessmann heat-pump data locally.")
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Repeat every N seconds. Omit to collect one snapshot and exit.",
    )
    arguments = parser.parse_args()

    if arguments.interval == 0 and "HOMEDASH_VIESSMANN_INTERVAL" in os.environ:
        arguments.interval = HOMEDASH_VIESSMANN_INTERVAL

    next_run = time.monotonic()
    while True:
        started = datetime.now(timezone.utc)
        run_id = start_collection_run(DATABASE_PATH, "viessmann", started.isoformat())
        try:
            snapshot_count = collect_once()
            finished = datetime.now(timezone.utc)
            finish_collection_run(
                DATABASE_PATH,
                run_id,
                finished_at=finished.isoformat(),
                status="success",
                record_count=snapshot_count,
                duration_ms=int((finished - started).total_seconds() * 1000),
            )
            print(f"Collected {snapshot_count} Viessmann heat-pump snapshots.")
        except ViessmannProviderError as error:
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
