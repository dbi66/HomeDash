# HomeClimate Dashboard v0.5.3

HomeClimate Dashboard is a local Streamlit app for monitoring a Homematic IP heating system. It reads room temperatures, target temperatures, humidity, and underfloor-heating valve positions from a Homematic IP Access Point such as the HmIP-HAP2.

## Current Architecture

This release consolidates the project to a single runtime model:

- One Streamlit dashboard instance
- One SQLite database: `data/heating_data.db`
- One launcher script: `scripts/run_dashboard.sh`
- One Homematic collector process that records readings every 15 minutes
- One Viessmann collector process that records heat-pump snapshots every 30 minutes
- One user-level systemd service for autostart on boot

The older development/production split was removed to simplify deployment and maintenance.

The app is read-only with respect to heating settings. It reports target temperatures but never writes them back to Homematic IP.

## Current Features

- Live Homematic IP room readings
- Mock provider for development without hardware
- Room overview grouped by `Obergeschoss` and `Erdgeschoss`
- Compact room tiles with:
  - Current temperature
  - Humidity
  - Target temperature
  - Valve thermometer, mapped from the associated floor-heating controller channel
  - Five-state temperature and humidity trend arrows calculated over the last 30 minutes: red `↑`, orange `↗`, gray `→`, light-blue `↘`, and blue `↓`
- Room detail view with historical charts and event log
- Compact charts for all rooms
- Room report with spider charts for current temperature and humidity across all rooms
- Single-service user setup with automatic startup and stable LAN access
- Graph scale defaults:
  - Temperature: `10-30 C`
  - Humidity and valve position: `0-100%`
  - Optional `Fit data` mode
- Homematic device and channel hierarchy in `Einstellungen`
- Read-only Viessmann inventory for installations, gateways, devices, and exposed feature names
- Local or trusted-network access through the dashboard launcher
- SQLite history for room readings, events, target reports, and Homematic snapshots
- Seven-day weather forecast for Aystetten (86482)
- Tile-based Home start page with room, weather, and heat-pump summaries
- Viessmann heat-pump schematics, KPIs, heating curve, and energy indicators
- Page-specific help and a rerender-only `Neu laden` action

## Navigation

The top navigation provides:

- `Home`: tile-based start page with weather, heat-pump, data-status, and room summaries
- `Raumdetail`: selected room history, charts, and event log
- `Raumbericht`: current temperature and humidity spider charts for all rooms
- `Alle Diagramme`: compact historical charts for all rooms
- `Wärmepumpe`: human-readable read-only report for archived Viessmann heat-pump data and snapshot history
- `Wetter`: seven-day forecast for Aystetten (86482)
- `Einstellungen`: reread Homematic devices, inspect the device/channel hierarchy, and load Viessmann data
- `Neu laden`: rerender the current page without triggering provider requests
- `Hilfe`: explains the current page and its data-update behavior

Click a room tile from `Home` to open its detail view.

### Viessmann read-only inventory

Installations with a Vitocal/Vitocell system can be inspected through PyViCare. Create an API key or client ID at the [Viessmann Climate Solutions Developer Portal](https://developer.viessmann-climatesolutions.com/start.html), then open `Einstellungen`, select the `Viessmann` tab, and enter the account email, password, API client ID, and token-file path:

```bash
export VIESSMANN_USERNAME="your-account-email"
export VIESSMANN_PASSWORD="your-account-password"
export VIESSMANN_CLIENT_ID="your-api-client-id"
export VIESSMANN_TOKEN_FILE="data/vicare_token.json"
```

Choose `Viessmann-Daten einlesen` to archive the complete feature inventory in `viessmann_snapshots`. Choose `Wärmepumpe read-only einlesen` to read and archive the current heat-pump feature values. Open `Wärmepumpe` in the main navigation for the human-readable report and stored snapshot history. The module selects Viessmann heat-pump devices only, reads their exposed feature properties, and never calls a Viessmann write API or changes heating settings. Credentials and live heat-pump values remain in the current Streamlit session; the token file remains local. Environment variables remain available for unattended use.

`scripts/run_dashboard.sh` also starts `scripts/collect_viessmann.py` in the background, which archives a Viessmann heat-pump snapshot every 30 minutes (override with `HOMEDASH_VIESSMANN_INTERVAL`, in seconds). It authenticates using the `VIESSMANN_USERNAME`, `VIESSMANN_PASSWORD`, `VIESSMANN_CLIENT_ID`, and `VIESSMANN_TOKEN_FILE` environment variables. The tracked systemd template loads them from `/home/dennis/.config/homedash/viessmann.env`; keep that file owner-readable only and never commit it.

The Homematic collector runs every 15 minutes by default. The dashboard `Neu laden` button only rerenders the current page and never triggers a provider request. Development checks are available with `python -m pytest -q` and `python -m ruff check app.py src scripts tests`.

## Prioritized Roadmap

The following ten steps are ordered by operational risk first, then by user value and maintainability. Each step should be completed with tests and a short system check before starting the next one.

1. **Make data freshness and failures explicit**
  Add a shared health model for Homematic, Viessmann, and weather data. Show `aktuell`, `veraltet`, `keine Daten`, rate-limit errors, and the last successful collection time consistently on every relevant page.

2. **Build a central alarm and status center**
  Combine stale data, offline devices, open valves, rooms below target, active heating rod, abnormal temperatures, and collector failures into one prioritized status tile on `Home`.

3. **Add reliable energy and cost analytics**
  Track daily, weekly, and monthly supplied energy, produced heat, SPF/COP, heating-rod share, hot-water share, and configurable electricity costs. Clearly distinguish calendar-day counters from rolling 24-hour values.

4. **Add cross-module heating effectiveness analysis**
  Correlate weather, heating curve, supply temperature, room temperatures, target temperatures, and valve positions. Highlight rooms that remain below target despite active heating demand.

5. **Complete operational maintenance metrics**
  Add compressor cycling, average runtime per start, fan/pump runtime, defrost count and duration, operating-mode history, and maintenance warnings.

6. **Split the Streamlit application into page modules**
  Move Home, Wetter, Wärmepumpe, Raumdetail, and reports out of `app.py`. Keep routing, shared session state, and common layout in a small application shell.

7. **Introduce typed domain and provider models**
  Replace untyped `dict[str, object]` payloads and scattered feature-name strings with typed room, weather, heat-pump, KPI, and sensor-mapping models. Keep provider-specific raw JSON behind adapters.

8. **Create a repository and migration layer for SQLite**
  Separate SQL, migrations, JSON decoding, and domain logic. Add schema versions, transaction boundaries, retention policies, and indexes for time-window KPI queries.

9. **Expand automated quality and integration tests**
  Add provider fixtures, collector retry tests, sensor-mapping tests, KPI edge cases, stale-data tests, weather fallback tests, and browser smoke tests for desktop and mobile routes.

10. **Harden deployment and observability**
   Move all secrets to a protected EnvironmentFile, add structured rotating logs, health checks, graceful collector shutdown, backup verification, and a documented upgrade/rollback procedure.

## Requirements

- macOS or another Python 3 environment
- Python 3.9 or newer
- Homematic IP Access Point for live mode
- A local Homematic IP auth configuration for live mode

## Installation

```bash
git clone https://github.com/dbi66/HomeDash.git
cd HomeDash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Homematic IP Authentication

Generate a local auth configuration:

```bash
hmip_generate_auth_token
```

Enter the Access Point SGTIN and press the blue system button on the physical Access Point when requested. The command creates `config.ini` locally.

`config.ini` contains credentials and is ignored by Git. Do not share or commit it.

## Start Locally

Initialize the database and start the dashboard together with its data collector:

```bash
python3 scripts/init_db.py
sh scripts/run_dashboard.sh
```

Open:

```text
http://localhost:8501
```

Run the dashboard without Homematic hardware (UI only, no collector):

```bash
HOMEDASH_PROVIDER=mock streamlit run app.py
```

## Autostart

The project uses a single user service for automatic startup:

```bash
systemctl --user enable --now homedash.service
```

This service starts the dashboard and the collector together and binds to `0.0.0.0:8501`.

Check the service and collector status:

```bash
systemctl --user status homedash.service
```

## Start

There is one dashboard instance and one database in this release:

```bash
sh scripts/run_dashboard.sh
```

The dashboard uses `data/heating_data.db` by default. The launcher also starts the Homematic collector, which writes room readings every five minutes. Override the bind address, port, collector interval, provider, or database path with environment variables when needed.

## Trusted Network Access

The default launcher binds to all network interfaces. To access the dashboard from another device on the same trusted network or VPN, find the host's active LAN address:

```bash
hostname -I
```

Then open:

```text
http://<lan-address>:8501
```

The launcher provides no authentication and no HTTPS. Use it only on a trusted network and never expose it directly to the public internet.

## Data Collection

Collect one complete Homematic state snapshot:

```bash
python scripts/collect_snapshot.py
```

The dashboard launcher collects room readings continuously. By default it runs one collection every five minutes and limits full Homematic snapshots to one every 30 minutes:

```bash
HOMEDASH_COLLECTOR_INTERVAL=300 sh scripts/run_dashboard.sh
```

Room valve positions are read from the `FLOOR_TERMINAL_BLOCK_MECHANIC_CHANNEL` channels of the associated HmIP floor-heating controllers. The values are normalized to percentages and stored in `room_readings`; valve transitions are recorded in `room_events`.

Collect one snapshot manually without starting the dashboard:

```bash
python scripts/collect_snapshot.py
```

Inspect available Homematic devices and channels without printing credentials:

```bash
python scripts/inspect_homematic.py
```

## Database Safety

The active database is:

```text
data/heating_data.db
```

`python scripts/init_db.py` creates missing tables and applies small migrations. It does not delete, replace, or reset the existing database.

Create a consistent SQLite backup before maintenance:

```bash
python scripts/backup_database.py
```

Backups are written to `data/backups/`, which is ignored by Git. Use an explicit location when needed:

```bash
python scripts/backup_database.py --output /path/to/heating_data-backup.db
```

To use a different database path without changing source code:

```bash
HOMEDASH_DATABASE=/path/to/heating_data.db streamlit run app.py
```

## Database Tables

- `room_readings`: normalized room time series used by the dashboard
- `homematic_snapshots`: deduplicated device, channel, and group snapshots stored as JSON
- `room_events`: valve opening/closing and externally observed target-temperature changes
- `target_changes`: retained for compatibility with earlier versions; the current app does not write target temperatures
- `viessmann_snapshots`: read-only Viessmann feature inventories stored as JSON

## Project Structure

```text
HomeDash/
|-- app.py
|-- data/
|   `-- heating_data.db
|-- src/
|   |-- config.py
|   |-- database.py
|   |-- history.py
|   |-- hmip_provider.py
|   |-- mock_provider.py
|   |-- models.py
|   `-- room_layout.py
|-- scripts/
|   |-- backup_database.py
|   |-- collect_snapshot.py
|   |-- init_db.py
|   |-- inspect_homematic.py
|   `-- run_dashboard.sh
|-- requirements.txt
`-- README.md
```

## Roadmap

- More complete room-level assignments
- Dew-point and temperature/humidity risk analysis
- Longer-term aggregation and retention policies
- Viessmann heat-pump integration
