import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = Path(os.getenv("HOMEDASH_DATABASE", DATA_DIR / "heating_data.db"))
CONFIG_PATH = Path(os.getenv("HOMEDASH_CONFIG", PROJECT_ROOT / "config.ini"))
PROVIDER = os.getenv("HOMEDASH_PROVIDER", "homematic" if CONFIG_PATH.exists() else "mock").lower()
