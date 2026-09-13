import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATABASE_PATH
from src.database import initialize_database


if __name__ == "__main__":
    initialize_database(DATABASE_PATH)
    print(f"Initialized database at {DATABASE_PATH}")
