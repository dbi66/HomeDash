# HomeClimate Dashboard 0.9a

**Prerelease:** Die `0.9a`-Version bündelt die aktuelle modulare Dashboard-Architektur, die mobile UI-Überarbeitung und die erste betriebliche Zugriffsmöglichkeit über Tailscale.

Lokales Streamlit-Dashboard zur Beobachtung einer Homematic-IP-Heizung und optional einer Viessmann-Wärmepumpe. Die Anwendung liest Daten, speichert sie lokal in SQLite und verändert keine Heizungs- oder Geräteeinstellungen.

## Funktionen

- Raumübersicht nach Etage mit Temperatur, Luftfeuchte, Zieltemperatur, Ventilstellung und Trends
- Raumdetail mit Historie, Diagrammen und Ereignissen
- Raumbericht und Diagramme für alle Räume
- Wettervorhersage für Aystetten (Open-Meteo)
- Viessmann-Inventory, Wärmepumpenbericht, Systemübersicht und Energiekennzahlen
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
               +-> Collector -> data/heating_data.db -> Streamlit-App
Viessmann API -┘                                      +-> HomeDash UI
Open-Meteo API ---------------------------------------> Wetterseite
```

- `app.py` ist der dünne Einstiegspunkt und Router.
- `src/` enthält Provider, Datenmodelle, Repository-Zugriff, Berechnungen und Views.
- `scripts/collect_snapshot.py` speichert Homematic-Raumwerte und Snapshots.
- `scripts/collect_viessmann.py` speichert Viessmann-Wärmepumpen-Snapshots.
- `scripts/run_dashboard.sh` startet beide Collector und Streamlit in einem Prozessverbund.
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

Für den vollständigen Betrieb mit beiden Collectors:

```bash
sh scripts/run_dashboard.sh
```

Danach öffnen:

```text
http://localhost:8501
```

Auf einem vertrauenswürdigen LAN-Gerät:

```text
http://<server-ip>:8501
```

Der Launcher verwendet standardmäßig `.venv/bin/python`, `0.0.0.0:8501`, die Datenbank `data/heating_data.db`, einen Homematic-Collector alle 900 Sekunden und einen Viessmann-Collector alle 1800 Sekunden.

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
| `HOMEDASH_RUN_COLLECTORS` | `1` | Collector-Prozesse aktivieren; für reine Test-UI auf `0` setzen |
| `HOMEDASH_ELECTRICITY_PRICE` | `0.30` | Preis in EUR/kWh für Kostenkennzahlen |
| `HOMEDASH_CONFIG` | `config.ini` | Pfad zur Homematic-Konfiguration |
| `VIESSMANN_TOKEN_FILE` | keine | Lokaler PyViCare-Token |

Beispiel für einen alternativen Port:

```bash
HOMEDASH_PORT=8502 sh scripts/run_dashboard.sh
```

Für die Migration ist `8503` als Testport reserviert. Bis der neue Stack eigene Collector besitzt, bleibt ausschließlich der produktive Dienst auf `8501` datenaktiv. Eine reine Test-UI darf keine Homematic- oder Viessmann-Abfragen starten:

```bash
HOMEDASH_PORT=8503 HOMEDASH_RUN_COLLECTORS=0 sh scripts/run_dashboard.sh
```

Der produktive Dienst auf `8501` bleibt dabei unverändert aktiv und ist der einzige Prozess, der Provider abfragt und die operative Datenbank aktualisiert. Niemals beide Ports mit aktivierten Collectors starten.

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

Die Anzeige „Stromverbrauch nicht gemeldet“ bedeutet, dass Viessmann aktuell einen elektrischen Tagesverbrauch von `0 kWh` oder keinen verwertbaren Wert liefert. Das ist nicht automatisch ein Fehler der App; die Rohdaten und deren Aktualität sollten geprüft werden.

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

## Migration nach 0.9a

Die Streamlit-Version `0.9a` ist als `v0.9a` archiviert. Die schrittweise Zielarchitektur mit FastAPI, SvelteKit, unabhängigen Collectors, SQLite-Migrationen, Parallelbetrieb und Rollback ist in [MIGRATION_PLAN.md](MIGRATION_PLAN.md) beschrieben.

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
├── app.py
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
│   ├── run_dashboard.sh
│   ├── smoke_test.py
│   └── homedash.service
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

## 0.9a bekannte Einschränkungen

- Viessmann kann elektrische Tagesverbrauchswerte mit `0 kWh` oder veralteten Quellzeitstempeln liefern, obwohl Wärmeerzeugung vorhanden ist. Die App zeigt diesen Zustand ausdrücklich an und erfindet keinen Verbrauchswert.
- Viessmann-Sensoren werden innerhalb eines Snapshots nicht immer gleichzeitig aktualisiert. Wärmepumpenschemata zeigen deshalb die jeweiligen Sensorzeitpunkte neben den Messwerten.
- SQLite-Schema-Versionierung, Aufbewahrungsregeln und ein dokumentierter Upgrade-/Rollback-Prozess sind nach dem Prerelease weiterhin offene Betriebsaufgaben.
