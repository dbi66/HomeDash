import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATABASE_PATH
from src.database import backup_database


BACKUP_DIR = PROJECT_ROOT / "data" / "backups"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a consistent HomeDash SQLite backup.")
    parser.add_argument("--output", type=Path, help="Explicit backup path.")
    parser.add_argument("--verify", action="store_true", help="Run SQLite integrity_check after backup.")
    arguments = parser.parse_args()

    output = arguments.output or BACKUP_DIR / f"heating_data-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    backup_database(DATABASE_PATH, output)
    print(f"Backup created: {output}")
    if arguments.verify:
        with sqlite3.connect(output) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"Backup integrity check failed: {result}")
        print("Backup integrity: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
