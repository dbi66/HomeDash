import argparse
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATABASE_PATH
from src.database import save_viessmann_snapshots
from src.viessmann_heatpump import read_heat_pumps
from src.viessmann_provider import ViessmannProviderError, load_client


def collect_once() -> int:
    client = load_client()
    heat_pumps = read_heat_pumps(client)
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

    next_run = time.monotonic()
    while True:
        try:
            snapshot_count = collect_once()
            print(f"Collected {snapshot_count} Viessmann heat-pump snapshots.")
        except ViessmannProviderError as error:
            print(f"Collection failed: {error}")
            if arguments.interval <= 0:
                return 1
        except Exception as error:
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
