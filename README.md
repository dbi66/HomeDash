# HomeClimate Dashboard 0.99a

`0.99a` ist der aktuelle Pre-Release-Stand von HomeDash mit FastAPI-Backend, statischer Dashboard-Oberfläche, mobilen Diagrammen und getrennten Collectors. Der produktive Dienst läuft bereits auf diesem Stack; die Version dient der Abnahme vor `1.0.0`.

HomeDash beobachtet eine Homematic-IP-Heizung und eine Viessmann-Wärmepumpe. Die produktive API und UI lesen SQLite; nur die beiden Collector schreiben neue Messwerte. Heizungs- oder Geräteeinstellungen werden nicht verändert.

## Aktueller Status

Stand: 2026-09-22. Der produktive Dienst läuft auf `8501` mit `backend.api:app`, genau einem Homematic-Collector und genau einem Viessmann-Collector. Die Datenbank ist erreichbar, die Warmwasser- und Pufferspeicherberichte liefern jeweils 24-Stunden-Historien, der Healthcheck ist grün und die Testsuite läuft mit `39 passed`.

## Offene Punkte vor 1.0.0

- Beide Wärmepumpen-Schemata benötigen eine visuelle Optimierung. Die aktuelle Darstellung ist funktional, aber noch nicht ausreichend klar, ruhig und hochwertig.
- SQLite-Schema-Versionierung, Aufbewahrungsregeln und ein dokumentierter Upgrade-/Rollback-Prozess fehlen noch.
- Nicht unterstützte Homematic-Funktionskanäle werden im Collector-Log gemeldet und sollten für einen ruhigeren Betrieb bewertet werden.
- Ein eigenes Favicon fehlt noch; der Dienst beantwortet `favicon.ico` derzeit mit `404`.

## Funktionen

- Raumübersicht nach Etage mit Temperatur, Luftfeuchte, Zieltemperatur, Ventilstellung und Trends
- Raumdetail mit Historie, Diagrammen und Ereignissen
- Raumbericht und Diagramme für alle Räume
- Wetterbericht für Aystetten (Open-Meteo) mit aktuellen Bedingungen, stündlichem Temperaturverlauf für heute und 7-Tage-Prognose
- Optionaler Viessmann-Außentemperatursensor direkt im Wetterbericht
- Viessmann-Inventory, Wärmepumpenbericht, Systemübersicht und Energiekennzahlen
- Warmwasserspeicher-Temperatur als KPI im Home- und Wärmepumpen-Dashboard
- 24-Stunden-Verläufe für Warmwasserspeicher und Pufferspeicher im Wärmepumpenbericht
- Kompakter Betriebsstand-Indikator in der oberen Navigation
- Systemstatus für veraltete Daten, Heizprobleme und fehlende Verbrauchswerte
- Mock-Modus für Entwicklung ohne Homematic-Hardware
- Responsive Darstellung für Desktop und mobile Browser
- Lokale SQLite-Historie und verifizierbare Backups
- Kompakte mobile Kennzahlen und Raumkarten ohne horizontales Überlaufen
- Gemeinsame Messreihen-Auswahl in „Alle Diagramme“ statt wiederholter Diagrammsteuerungen
- Zeitstempel direkt an Viessmann-Sensorwerten, wenn Messwerte nicht synchron aktualisiert wurden

## Architektur

```text
Homematic IP  -┐
               +-> Collector -> data/heating_data.db -> FastAPI + HomeDash UI
Viessmann API -┘                                      +-> Tailscale Serve
Open-Meteo API ---------------------------------------> Wetterseite
```

- `backend/` enthält die read-only FastAPI-API (`0.99a`).
- `frontend/` enthält die statische Dashboard-Oberfläche.
- `src/` enthält Provider, Datenmodelle, Repository-Zugriff, Berechnungen und Views.
- `scripts/collect_snapshot.py` speichert Homematic-Raumwerte und Snapshots.
- `scripts/collect_viessmann.py` speichert Viessmann-Wärmepumpen-Snapshots.
- `scripts/run_prod.sh` startet die produktive FastAPI-UI und genau einen Collector-Satz.
- `app.py` und `scripts/run_dashboard.sh` bleiben bis zum Abschluss der Rollback-Aufbewahrung archiviert.
- `data/heating_data.db` ist die Standarddatenbank und wird nicht ins Repository eingecheckt.

## Neuaufbau aus einem frischen Checkout

### 1. Repository und Python-Umgebung

Python 3.10 oder neuer wird benötigt. Die Anwendung verwendet Typannotationen mit `|` und setzt deshalb mindestens Python 3.10 voraus.

```bash
git clone https://github.com/dbi66/HomeDash.git
cd HomeDash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Für Entwicklung und Tests zusätzlich:

```bash
python -m pip install pytest ruff
```

### 2. Datenbank anlegen

```bash
python scripts/init_db.py
```

Der Befehl legt fehlende Tabellen an und führt vorhandene kleine Schema-Anpassungen aus. Bestehende Daten werden nicht gelöscht.

### 3. Homematic-IP-Zugang einrichten

Für den Live-Modus wird ein lokaler Homematic-IP-Access-Point benötigt:

```bash
hmip_generate_auth_token
```

SGTIN des Access Points eingeben und bei Aufforderung die blaue Systemtaste drücken. Dadurch entsteht lokal eine `config.ini`. Diese Datei enthält Zugangsdaten, darf nicht geteilt und nicht committed werden.

Ohne Hardware kann zunächst der Mock-Modus verwendet werden:

```bash
HOMEDASH_PROVIDER=mock python -m streamlit run app.py
```

### 4. Viessmann optional konfigurieren

Für die Viessmann-Integration werden Zugangsdaten und eine Client-ID benötigt. Die Werte gehören in eine lokale, nur für den Benutzer lesbare Datei, nicht in das Repository:

```bash
mkdir -p ~/.config/homedash
chmod 700 ~/.config/homedash
cat > ~/.config/homedash/viessmann.env <<'EOF'
VIESSMANN_USERNAME=account@example.com
VIESSMANN_PASSWORD=secret
VIESSMANN_CLIENT_ID=client-id
VIESSMANN_TOKEN_FILE=/absolute/path/to/HomeDash/data/vicare_token.json
EOF
chmod 600 ~/.config/homedash/viessmann.env
```

Die Viessmann-Integration ist read-only. Sie liest die verfügbaren Features und schreibt keine Heizungsparameter.

### 5. App starten

Für den produktiven Betrieb:

```bash
systemctl --user restart homedash.service
```

Danach öffnen:

```text
http://localhost:8501
```

Auf einem vertrauenswürdigen LAN-Gerät:

```text
http://<server-ip>:8501
```

Der produktive User-Service verwendet `.venv/bin/python`, bindet `0.0.0.0:8501`, liest `data/heating_data.db` und startet genau einen Homematic-Collector alle 900 Sekunden sowie einen Viessmann-Collector alle 1800 Sekunden. Ein `flock` verhindert einen zweiten Collector-Satz.

Nur die UI starten:

```bash
HOMEDASH_PROVIDER=mock .venv/bin/python -m streamlit run app.py --server.headless true
```

## Konfiguration

Alle Variablen sind optional:

| Variable | Standard | Zweck |
| --- | --- | --- |
| `HOMEDASH_PROVIDER` | `homematic` bei vorhandener `config.ini`, sonst `mock` | Datenprovider der UI |
| `HOMEDASH_DATABASE` | `data/heating_data.db` | SQLite-Datei |
| `HOMEDASH_BIND` | `0.0.0.0` | Bind-Adresse des Launchers |
| `HOMEDASH_PORT` | `8501` | HTTP-Port |
| `HOMEDASH_COLLECTOR_INTERVAL` | `900` | Homematic-Abfrage in Sekunden |
| `HOMEDASH_VIESSMANN_INTERVAL` | `1800` | Viessmann-Abfrage in Sekunden |
| `HOMEDASH_PROVIDER_TIMEOUT_SECONDS` | `30` | Maximale Dauer eines Provideraufrufs vor Retry |
| `HOMEDASH_RUN_COLLECTORS` | `1` | Collector-Prozesse aktivieren; für reine Test-UI auf `0` setzen |
| `HOMEDASH_ELECTRICITY_PRICE` | `0.30` | Preis in EUR/kWh für Kostenkennzahlen |
| `HOMEDASH_CONFIG` | `config.ini` | Pfad zur Homematic-Konfiguration |
| `VIESSMANN_TOKEN_FILE` | keine | Lokaler PyViCare-Token |

Beispiel für einen alternativen Port:

```bash
HOMEDASH_PORT=8502 sh scripts/run_dashboard.sh
```

`8503` ist der read-only Testport. Dort laufen keine Collector und keine Provider-Abfragen:

```bash
HOMEDASH_PORT=8503 HOMEDASH_RUN_COLLECTORS=0 sh scripts/run_dashboard.sh
```

Der produktive Dienst auf `8501` ist der einzige Prozess, der Provider abfragt und die operative Datenbank aktualisiert. Niemals `8503` mit Collectors starten.

Die API kann auf `8503` testweise gestartet werden:

```bash
.venv/bin/uvicorn backend.api:app --host 0.0.0.0 --port 8503
```

Verfügbare Endpunkte sind `/health/live`, `/health/ready`, `/api/v1/home`, `/api/v1/status`, `/api/v1/rooms`, Raumhistorien, `/api/v1/heat-pump`, `/api/v1/heat-pump/report` und `/api/v1/weather`. Der Wetter-Endpunkt liefert aktuelle Bedingungen, stündliche Werte für den 7-Tage-Zeitraum, Tagesprognosen sowie den optionalen Viessmann-Außensensor. Die API öffnet SQLite ausschließlich read-only.

## Daten und Collector

Einmalige Homematic-Abfrage:

```bash
python scripts/collect_snapshot.py
```

Einmalige Viessmann-Abfrage:

```bash
python scripts/collect_viessmann.py
```

Geräte und Kanäle untersuchen:

```bash
python scripts/inspect_homematic.py
```

Gespeichert werden unter anderem:

- `room_readings`: normalisierte Raumzeitreihe
- `homematic_snapshots`: deduplizierte Homematic-Snapshots als JSON
- `room_events`: beobachtete Ventil- und Raumereignisse
- `target_changes`: Kompatibilitätstabelle; die App schreibt keine Zieltemperaturen
- `viessmann_snapshots`: read-only Viessmann-Features als JSON

Die Collector protokollieren Erfolg, Fehler, Laufzeit und Datensatzanzahl in `collection_runs`. Veraltete oder fehlende Providerläufe erscheinen im Statusbericht.

## Externer Zugriff über Tailscale

Für den Zugriff von unterwegs wird Tailscale empfohlen. Die App bleibt dabei im privaten Tailnet und wird nicht per Router-Portfreigabe öffentlich gemacht.

Auf dem Server:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
sudo tailscale set --operator="$USER"
tailscale serve --bg http://127.0.0.1:8501
tailscale serve status
```

Die ausgegebene `https://...ts.net`-Adresse kann im mobilen Browser verwendet werden. Auf dem iPhone muss die Tailscale-App installiert, aktiviert und mit demselben Tailnet-Konto angemeldet sein. Die konkrete Adresse ist installationsabhängig und gehört nicht fest in die Projektdokumentation.

Der aktuelle Tailscale-Zugriff ist auf das Dashboard begrenzt. Eine spätere Verschärfung kann HomeDash zusätzlich ausschließlich an `127.0.0.1` binden; der Tailscale-Serve-Proxy bleibt dann der einzige externe Einstiegspunkt.

## Release und Rollback

Der aktuelle Stand ist `0.99a` Pre-Release. Die frühere Streamlit-Version `0.9a` ist als `v0.9a` archiviert. Der Produktionsbaum vor der Strukturbereinigung ist zusätzlich mit `pre-cleanup-20260922` markiert.

Bei Problemen wird der User-Service gestoppt und der archivierte Streamlit-Fallback aus `v0.9a` wiederhergestellt; Tailscale bleibt auf `8501`.

## Systemd-Betrieb

Das Template `scripts/homedash.service` ist für einen Benutzer-Service vorbereitet. Vor der Aktivierung müssen `WorkingDirectory`, Datenbankpfad und der Pfad zur geschützten Viessmann-Environment-Datei zur Installation passen.

```bash
mkdir -p ~/.config/systemd/user
cp scripts/homedash.service ~/.config/systemd/user/homedash.service
systemctl --user daemon-reload
systemctl --user enable --now homedash.service
systemctl --user status homedash.service
```

Logs anzeigen:

```bash
journalctl --user -u homedash.service -f
```

Der Service ist für ein vertrauenswürdiges Netzwerk gedacht. Es gibt keine integrierte Authentifizierung und kein HTTPS. Nicht direkt ins Internet exponieren.

## Backup, Healthcheck und Tests

Konsistentes SQLite-Backup:

```bash
python scripts/backup_database.py --verify
```

Betriebsprüfung und HTTP-Smoke-Test:

```bash
python scripts/healthcheck.py
python scripts/smoke_test.py
```

Qualitätsprüfungen:

```bash
python -m pytest -q
python -m ruff check app.py src scripts tests
```

## Troubleshooting

### Browser zeigt keine App

```bash
ss -lntp | grep 8501
curl -I http://127.0.0.1:8501
```

Wenn der Port belegt ist, einen anderen Port verwenden:

```bash
HOMEDASH_PORT=8502 sh scripts/run_dashboard.sh
```

### Keine Homematic-Daten

- Prüfen, ob `config.ini` existiert und lokal lesbar ist.
- Access Point und Netzwerkverbindung prüfen.
- Eine Einzelabfrage mit `python scripts/collect_snapshot.py` ausführen.
- Für UI-Tests `HOMEDASH_PROVIDER=mock` verwenden.

### Keine Viessmann-Daten

- `VIESSMANN_USERNAME`, `VIESSMANN_PASSWORD`, `VIESSMANN_CLIENT_ID` und `VIESSMANN_TOKEN_FILE` prüfen.
- Rechte der Environment-Datei und Token-Datei prüfen.
- `python scripts/collect_viessmann.py` einmalig ausführen und die Fehlermeldung prüfen.
- In der App unter `Einstellungen` die read-only Inventory-Abfrage ausführen.

## Projektstruktur

```text
HomeDash/
├── app.py                    # archivierter Streamlit-Fallback
├── config.ini                 # lokal, geheim, nicht teilen
├── requirements.txt
├── data/
│   ├── heating_data.db        # Laufzeitdaten, lokal
│   └── vicare_token.json      # optional, lokal
├── scripts/
│   ├── backup_database.py
│   ├── collect_snapshot.py
│   ├── collect_viessmann.py
│   ├── healthcheck.py
│   ├── init_db.py
│   ├── inspect_homematic.py
│   ├── run_dashboard.sh       # archivierter Streamlit-Fallback
│   ├── run_prod.sh
│   ├── smoke_test.py
│   └── homedash.service
├── backend/
│   ├── __init__.py
│   └── api.py                  # read-only FastAPI-API
├── frontend/
│   ├── app.js
│   └── index.html
├── src/
│   ├── app_shell.py           # Header und Navigation
│   ├── database.py             # SQLite-Zugriff und Schema
│   ├── home_dashboard.py       # Home-Seite
│   ├── monitoring.py           # Status- und Energiekennzahlen
│   ├── models.py               # Domänenmodelle
│   ├── repository.py            # Lesezugriff
│   ├── viessmann_*.py          # Viessmann-Adapter und Reports
│   ├── weather*.py             # Wetterprovider und Ansicht
│   └── ui_theme.py              # Responsive CSS
└── tests/
```

## Lizenz und Sicherheit

Das Dashboard ist für den lokalen bzw. vertrauenswürdigen Netzwerkbetrieb ausgelegt. Zugangsdaten, Token, `config.ini`, Environment-Dateien und Datenbank-Backups gehören nicht in Git. Vor Wartung oder Migration immer ein Backup erstellen.

## 0.99a bekannte Einschränkungen

- Viessmann kann elektrische Tagesverbrauchswerte mit `0 kWh` oder veralteten Quellzeitstempeln liefern, obwohl Wärmeerzeugung vorhanden ist. Die App zeigt diesen Zustand ausdrücklich an und erfindet keinen Verbrauchswert.
- Viessmann-Sensoren werden innerhalb eines Snapshots nicht immer gleichzeitig aktualisiert. Wärmepumpenschemata zeigen deshalb die jeweiligen Sensorzeitpunkte neben den Messwerten.
- Die vollständige Liste der offenen Punkte steht im Abschnitt „Offene Punkte vor 1.0.0“.
