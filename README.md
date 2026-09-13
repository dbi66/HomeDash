# HomeClimate Dashboard v0.3

HomeClimate Dashboard is a local Streamlit app for monitoring a Homematic IP heating system. It reads room temperatures, target temperatures, humidity, and underfloor-heating valve positions from a Homematic IP Access Point such as the HmIP-HAP2.

The app is read-only with respect to heating settings. It reports target temperatures but never writes them back to Homematic IP.

## Current Features

- Live Homematic IP room readings
- Mock provider for development without hardware
- Room overview grouped by `Obergeschoss` and `Erdgeschoss`
- Compact room tiles with:
  - Current temperature
  - Humidity
  - Target temperature
  - Valve thermometer
  - Five-state temperature and humidity trend arrows: red `↑`, orange `↗`, gray `→`, light-blue `↘`, and blue `↓`
- Room detail view with historical charts and event log
- Compact charts for all rooms
- Graph scale defaults:
  - Temperature: `10-30 C`
  - Humidity and valve position: `0-100%`
  - Optional `Fit data` mode
- Homematic device and channel hierarchy in `Einstellungen`
- Read-only Viessmann inventory for installations, gateways, devices, and exposed feature names
- Local or trusted-network access through the dashboard launcher
- SQLite history for room readings, events, target reports, and Homematic snapshots

## Navigation

The top navigation provides:

- `Home`: room overview only
- `Raumdetail`: selected room history, charts, and event log
- `Alle Diagramme`: compact historical charts for all rooms
- `Einstellungen`: reread Homematic devices, inspect the device/channel hierarchy, and load Viessmann data
- `Refresh`: fetch and archive current readings

Click a room tile from `Home` to open its detail view.

### Viessmann read-only inventory

Installations with a Vitocal/Vitocell system can be inspected through PyViCare. Configure credentials only through local environment variables:

```bash
export VIESSMANN_USERNAME="your-account-email"
export VIESSMANN_PASSWORD="your-account-password"
export VIESSMANN_CLIENT_ID="your-api-client-id"
export VIESSMANN_TOKEN_FILE="data/vicare_token.json"
```

Then open `Einstellungen` and choose `Viessmann-Daten einlesen`. The integration archives the complete feature inventory in `viessmann_snapshots` and never changes heating settings. Credentials and the token file remain local.

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

Initialize the database and start Streamlit:

```bash
python scripts/init_db.py
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

Run without Homematic hardware:

```bash
HOMEDASH_PROVIDER=mock streamlit run app.py
```

## Trusted Network Access

The default launcher binds to localhost. To access the dashboard from another device on the same trusted network or VPN:

```bash
HOMEDASH_BIND=0.0.0.0 HOMEDASH_PORT=8501 sh scripts/run_dashboard.sh
```

Find the Mac's active address:

```bash
ifconfig | awk '/inet / && $2 != "127.0.0.1" {print $2}'
```

Then open:

```text
http://<mac-address>:8501
```

The launcher provides no authentication and no HTTPS. Never expose this development server directly to the public internet.

## Data Collection

Collect one complete Homematic state snapshot:

```bash
python scripts/collect_snapshot.py
```

Collect room readings continuously and limit full Homematic snapshots to one every 30 minutes:

```bash
python scripts/collect_snapshot.py --interval 300
```

Change the full snapshot interval:

```bash
python scripts/collect_snapshot.py --interval 300 --snapshot-interval 60
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

- Automatic macOS LaunchDaemon setup for the collector
- More complete room-level assignments
- Dew-point and temperature/humidity risk analysis
- Longer-term aggregation and retention policies
- Viessmann heat-pump integration
