# HomeClimate Dashboard

A local Python control center for monitoring and understanding your home's heating system.

HomeClimate Dashboard collects data from a Homematic IP Access Point, with a focus on underfloor heating. It is designed for long-term storage and historical analysis, with enough room to keep at least 12 months of heating data. The architecture is also prepared for a future Viessmann heat pump integration.

The first two milestones are now runnable. The dashboard uses Homematic IP when a local `config.ini` is present and falls back to deterministic mock readings otherwise. Mock mode is still available with `HOMEDASH_PROVIDER=mock`.

## What it does

- **Live monitoring:** Display current and target room temperatures, humidity, and valve opening percentages.
- **Local data storage:** Persist telemetry in a local SQLite database so you can build a heating history that lasts more than a year.
- **Trend analysis:** Explore warm-up phases, room cooldown behavior, and valve activity with interactive Streamlit charts across days, weeks, months, and years.

## Tech stack

- **Frontend:** Streamlit
- **Backend:** Python 3, optimized for Apple Silicon and macOS
- **APIs:** `homematicip` for the Homematic IP Cloud; `PyViCare` is planned for the future Viessmann integration
- **Storage and analysis:** SQLite and Pandas, with no external database server required

## Getting started

### 1. Clone the repository and create an environment

```bash
git clone https://github.com/dbi66/HomeDash.git
cd HomeDash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Authenticate with Homematic IP

Generate an auth token for local access to your Access Point:

```bash
hmip_generate_auth_token
```

The script asks for the Access Point's SGTIN. When prompted, press the blue system button on the physical device. The generated configuration is stored locally.

### 3. Initialize the database and start the app

```bash
python scripts/init_db.py
streamlit run app.py
```

The dashboard starts at `http://localhost:8501`. With Homematic IP configured, use **Refresh readings** to fetch the latest room data from the cloud and store it locally. To run without hardware, use:

```bash
HOMEDASH_PROVIDER=mock streamlit run app.py
```

Keep `config.ini` local. It contains the Homematic IP auth token and is excluded from Git.

To inspect the data exposed by the Homematic system without printing credentials, run:

```bash
python scripts/inspect_homematic.py
```

The dashboard currently groups `Living Room` under `Upstairs` and `Arbeit Dennis` under `Base level`. The aliases `Wohnzimmer` -> `Living Room` and `Küche` -> `Kitchen` are merged automatically. Rooms without an explicit mapping appear under `Unassigned` until their level is confirmed.

## Project structure

```text
HomeDash/
|-- app.py                 # Main Streamlit dashboard
|-- data/
|   `-- heating_data.db    # Locally generated SQLite database
|-- src/
|   |-- database.py        # SQLite read and write operations
|   |-- hmip_provider.py   # Homematic IP connection and room mapping
|   |-- mock_provider.py   # Deterministic room readings for development
|   |-- models.py          # Shared room reading model
|   |-- room_layout.py      # Building-level room assignments
|   `-- __init__.py
|-- scripts/
|   |-- init_db.py         # Database initialization script
|   `-- inspect_homematic.py # Homematic data inventory helper
|-- requirements.txt       # Project dependencies
`-- README.md
```

## Roadmap

- [x] First end-to-end slice with mock readings, SQLite persistence, and Streamlit UI
- [x] Connect the dashboard to Homematic IP through a real client
- [x] Group dashboard rooms into base level and upstairs sections
- [x] Add a helper for inspecting available Homematic devices and data fields
- [ ] Map the remaining rooms to their building levels
- [ ] Read heating components such as wall thermostats and underfloor heating controllers, then show them live
- [ ] Add a data logger that writes values to SQLite every minute or hour, using a macOS LaunchDaemon or background loop
- [ ] Add interactive historical views with Pandas DataFrames and Streamlit line charts
- [ ] Integrate the Viessmann API through PyViCare to track flow temperature, return temperature, and compressor status for the Vitocal 250-A
- [ ] Analyze correlations, such as how an open kitchen heating circuit affects the heat pump's flow temperature
- [ ] Extend the architecture to support more Homematic IP sensors and actuators