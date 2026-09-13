import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import initialize_database


if __name__ == "__main__":
    database_path = PROJECT_ROOT / "data" / "heating_data.db"
    initialize_database(database_path)
    print(f"Initialized database at {database_path}")
