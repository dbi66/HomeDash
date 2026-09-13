# HomeClimate Dashboard

A local Python control center for monitoring and understanding your home's heating system.

HomeClimate Dashboard collects data from a Homematic IP Access Point, with a focus on underfloor heating. It is designed for long-term storage and historical analysis, with enough room to keep at least 12 months of heating data. The architecture is also prepared for a future Viessmann heat pump integration.

The current build uses Homematic IP when a local `config.ini` is present and falls back to deterministic mock readings otherwise. It provides live room cards, building-level grouping, and a local archive of Homematic state. Mock mode is still available with `HOMEDASH_PROVIDER=mock`.

## What it does

- **Live monitoring:** Display current and target room temperatures, humidity, and valve opening percentages.
- **Local data storage:** Persist telemetry in a local SQLite database so you can build a heating history that lasts more than a year.
- **Trend analysis:** Explore warm-up phases, room cooldown behavior, and valve activity with interactive Streamlit charts across days, weeks, months, and years.

## Tech stack

- **Frontend:** Streamlit
- **Backend:** Python 3, optimized for Apple Silicon and macOS
- **APIs:** `homematicip` for the Homematic IP Cloud; `PyViCare` is planned for the future Viessmann integration
- **Storage and analysis:** SQLite and JSON snapshots, with no external database server required

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

### Remote access

The default server is local-only. To make the dashboard reachable from another device on a trusted home network or VPN:

```bash
HOMEDASH_BIND=0.0.0.0 HOMEDASH_PORT=8501 sh scripts/run_dashboard.sh
```

Find the Mac's LAN address with `ipconfig getifaddr en0`, then open `http://<mac-address>:8501` on the other device. The launcher does not add authentication or HTTPS, so do not expose this server directly to the public internet.

The room cards automatically switch to a compact two-column layout on narrow iPhone-sized screens. Tap any room tile to select it and load that room's historical charts.

Keep `config.ini` local. It contains the Homematic IP auth token and is excluded from Git.

To inspect the data exposed by the Homematic system without printing credentials, run:

```bash
python scripts/inspect_homematic.py
```

To archive the current state of every available Homematic device, functional channel, and group:

```bash
python scripts/collect_snapshot.py
```

For continuous collection every five minutes:

```bash
python scripts/collect_snapshot.py --interval 300
```

Full Homematic snapshots are deduplicated and limited to one every 30 minutes by default. Change that interval explicitly when needed:

```bash
python scripts/collect_snapshot.py --interval 300 --snapshot-interval 60
```

Snapshots are stored in the local `homematic_snapshots` SQLite table as JSON values. The HmIP cloud does not expose a historical backfill endpoint through the installed API, so historical coverage starts when collection begins.

The dashboard uses German room labels. `Kitchen` and `Küche` are displayed as `Küche`; `Living Room` and `Wohnzimmer` are displayed as `Wohnzimmer`. Rooms are grouped from the two FALMOT floor-heating controllers: `... - oben` becomes `Obergeschoss`, and `... - unten` becomes `Erdgeschoss`. Manual assignments override controller inference: `Esszimmer` is upstairs and `Vorratsraum` is on the ground floor. Rooms without a confirmed assignment, including `Schlafzimmer`, appear under `Nicht zugeordnet`.

The Home view shows the room overview only. Select a room to open its detail view with controls, history, and an event log. The detail charts use 10-30 C as the default temperature scale and 0-100% for humidity and valve values; **Fit data** is available when the fixed range is not useful. Valve openings and target-temperature changes are recorded as room events.

Open **Einstellungen** in the dashboard to reread the current Homematic IP devices. **Geraetehierarchie anzeigen** shows a graphical Home -> device -> channel tree with compact device cards and channel chips.

The selected room reports its current target temperature in the room card and history charts. HomeDash does not write target temperatures or other heating settings back to Homematic IP.

Use **Alle Diagramme** to open a compact overview of the historical temperature charts for every room. The selected time range applies to all rooms.

## Project structure

```text
HomeDash/
|-- app.py                 # Main Streamlit dashboard
|-- data/
|   `-- heating_data.db    # Locally generated SQLite database
|-- src/
|   |-- database.py        # SQLite read and write operations
|   |-- hmip_provider.py   # Homematic IP connection and room mapping
|   |-- history.py         # Full Homematic snapshot archive
|   |-- mock_provider.py   # Deterministic room readings for development
|   |-- models.py          # Shared room reading model
|   |-- room_layout.py      # Building-level room assignments
|   `-- __init__.py
|-- scripts/
|   |-- collect_snapshot.py # Historical snapshot collector
|   |-- init_db.py         # Database initialization script
|   |-- inspect_homematic.py # Homematic data inventory helper
|   `-- run_dashboard.sh    # Local or LAN Streamlit launcher
|-- requirements.txt       # Project dependencies
`-- README.md
```

## Roadmap

- [x] First end-to-end slice with mock readings, SQLite persistence, and Streamlit UI
- [x] Connect the dashboard to Homematic IP through a real client
- [x] Group dashboard rooms into Erdgeschoss and Obergeschoss sections
- [x] Add a helper for inspecting available Homematic devices and data fields
- [x] Archive full Homematic snapshots for future history and analysis
- [x] Add a one-shot and interval-based data collector
- [x] Add selectable historical temperature and valve charts
- [x] Add a compact mobile dashboard layout
- [x] Add a configurable local/LAN web server launcher
- [ ] Map the remaining rooms to their building levels
- [ ] Run the collector automatically through a macOS LaunchDaemon
- [ ] Integrate the Viessmann API through PyViCare to track flow temperature, return temperature, and compressor status for the Vitocal 250-A
- [ ] Analyze correlations, such as how an open kitchen heating circuit affects the heat pump's flow temperature
- [ ] Extend the architecture to support more Homematic IP sensors and actuators