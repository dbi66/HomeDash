import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATABASE_PATH
from src.database import backup_database


DEVELOPMENT_DATABASE_PATH = PROJECT_ROOT / "data" / "heating_data-test.db"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clone the production HomeDash database for development."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEVELOPMENT_DATABASE_PATH,
        help="Development database path (default: data/heating_data-test.db).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing development database.",
    )
    arguments = parser.parse_args()

    output = arguments.output
    if output.exists() and not arguments.force:
        raise SystemExit(f"Refusing to overwrite existing database: {output}. Use --force.")

    backup_database(DATABASE_PATH, output)
    print(f"Production database copied to: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
