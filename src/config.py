import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = Path(os.getenv("HOMEDASH_DATABASE", DATA_DIR / "heating_data.db"))
CONFIG_PATH = Path(os.getenv("HOMEDASH_CONFIG", PROJECT_ROOT / "config.ini"))
PROVIDER = os.getenv("HOMEDASH_PROVIDER", "homematic" if CONFIG_PATH.exists() else "mock").lower()
HOMEDASH_COLLECTOR_INTERVAL = int(os.getenv("HOMEDASH_COLLECTOR_INTERVAL", "900"))
HOMEDASH_VIESSMANN_INTERVAL = int(os.getenv("HOMEDASH_VIESSMANN_INTERVAL", "1800"))
HOMEDASH_PROVIDER_TIMEOUT_SECONDS = float(os.getenv("HOMEDASH_PROVIDER_TIMEOUT_SECONDS", "30"))
HOMEDASH_ELECTRICITY_PRICE = float(os.getenv("HOMEDASH_ELECTRICITY_PRICE", "0.30"))
