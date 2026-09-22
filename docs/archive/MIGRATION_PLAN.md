# HomeDash Migration Plan

## Ziel

HomeDash soll von der Streamlit-Anwendung zu einer klar getrennten Monitoring-Anwendung mit stabiler mobiler UI, testbarer API und unabhängigen Daten-Collector-Prozessen weiterentwickelt werden.

Die aktuelle Streamlit-Version bleibt als reproduzierbarer Referenzstand erhalten:

- Release: `0.9a`
- Git tag: `v0.9a`
- Commit: `706df7e`
- Status: validiert, auf GitHub veröffentlicht

Die Migration darf diesen Stand nicht verändern.

## Zielarchitektur

```text
Homematic IP ─┐
Viessmann    ─┼─> Provider Adapter ─> Collector Jobs ─> SQLite
Open-Meteo   ─┘                                      │
                                                     v
                                               FastAPI Backend
                                                     │
                                               SvelteKit UI
                                                     │
                                              Tailscale Serve
```

### Backend

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy oder SQLModel
- Alembic für Schema-Versionierung
- pytest und Ruff
- strukturierte JSON-Logs

Python bleibt wegen der vorhandenen Homematic-IP- und PyViCare-Integrationen die pragmatische Wahl.

### Frontend

- SvelteKit
- TypeScript
- ECharts oder Apache ECharts für Historien
- responsive Layout ohne Streamlit-CSS-Abhängigkeiten
- REST als Standard, Server-Sent Events optional für Live-Updates

SvelteKit wird gewählt, weil das Dashboard eine überschaubare Anwendung ist und eine kontrollierbare mobile UI wichtiger ist als ein großes Komponenten-Ökosystem.

### Datenbank

- SQLite mit WAL-Modus für den Einzelhaushalt
- Alembic-Migrationen
- Indizes auf `provider`, `device_id`, `sensor_id` und `recorded_at`
- Retention-Job für alte Rohdaten
- PostgreSQL erst bei mehreren Häusern, Benutzern oder externen Schreibzugriffen

## Migrationsprinzipien

1. `v0.9a` bleibt unverändert und jederzeit startbar.
2. Neue Komponenten werden parallel zur Streamlit-App entwickelt.
3. Provider- und Datenverträge werden zuerst stabilisiert.
4. Jede Phase endet mit Tests und einem nutzbaren Zwischenstand.
5. Kein Big-Bang-Rewrite.
6. Rollback bedeutet zunächst: Streamlit-Service und `v0.9a` wieder aktivieren.

## Phasen

### Phase 0: Archiv und Baseline

Status: abgeschlossen.

- `v0.9a` als annotiertes Git-Tag veröffentlicht
- Tests und Ruff erfolgreich
- aktueller Datenbankstand bleibt als Betriebsdatenbestand erhalten
- Streamlit bleibt der produktive Referenzdienst

### Phase 1: Verträge und Datenmodell

- Status: begonnen mit dem read-only FastAPI-Slice in `migration/api.py`.
- Domänenmodelle für Raum, Sensor, Snapshot, Providerstatus und Messwert definieren
- `recorded_at` und `source_timestamp` getrennt speichern
- `quality` und `is_stale` für jeden externen Messwert vorsehen
- Provider-Adapter von UI und Repository entkoppeln
- Contract-Tests für Homematic, Viessmann und Wetter schreiben

Ergebnis: Backend-unabhängige, testbare Datenverträge.

### Wiederanlaufstatus und produktiver Swap

Stand: 2026-09-20. Der produktive Swap auf `proxubuntu01` ist durchgeführt und verifiziert:

- `main` und `origin/main` zeigen auf denselben Commit.
- Die vollständige Testsuite ist grün; die Migrationstests validieren API, Read-only-Datenzugriff und den statischen UI-Einstieg.
- Die operative Datenbank ist vorhanden und wird von der Migrations-API ausschließlich lesend geöffnet.
- Der produktive Migrationsstand läuft auf `8501`; der aktuelle Code ist nach `origin/main` gepusht.
- Streamlit bleibt über `v0.9a` und den archivierten Service als Rollback-Basis erhalten.
- Tailscale Serve zeigt auf `http://127.0.0.1:8501`.
- `homedash.service` startet `migration.api:app` und genau einen Collector-Satz.
- Homematic und Viessmann schreiben erfolgreiche Runs in `collection_runs`.

Nächste Reihenfolge:

1. Erledigt: `8503` ohne Collector und der Browser-Smoke-Test für 320px, 390px, 768px und Desktop sind geprüft; Raumdetail, Historie und Wärmepumpenansicht funktionieren ohne horizontalen Überlauf.
2. Erledigt: Read-only-Ausgaben von `8503` und dem produktiven Repository-Pfad auf `8501` verglichen; 14 Räume und die Wärmepumpe stimmen überein.
3. Erledigt: Datenverträge für Sensor/Snapshot mit `source_timestamp`, `quality` und `is_stale` sowie Contract-Tests ergänzt.
4. Erledigt: Homematic- und Viessmann-Collector mit Retry, 30-Sekunden-Provider-Timeout, Backoff und `collection_runs` stabilisiert; die produktiven Prozesse benötigen für die Aktivierung einen kontrollierten Neustart.
5. Erledigt: produktiven Migration-Service auf `8501` umgeschaltet, Collector-Exklusivität geprüft und Tailscale-Zugriff verifiziert.
6. Als nächstes SQLite-WAL, Alembic, Retention und Restore auf einer Datenbankkopie als nachgelagerte Betriebsverbesserungen einführen.

### Phase 2: Collector und Persistenz

- Homematic-Collector als eigenständigen Prozess stabilisieren
- Viessmann-Collector als eigenständigen Prozess stabilisieren
- Retry, Backoff, Timeout und verständliche Fehlerzustände vereinheitlichen
- SQLite-WAL und Alembic einführen
- Aufbewahrungs- und Backup-Strategie dokumentieren
- `collection_runs` für Erfolg, Fehler, Laufzeit und Datenalter ergänzen

Ergebnis: zuverlässige Datenversorgung ohne Streamlit-Abhängigkeit.

### Phase 3: FastAPI-Backend

- Status: erster read-only Slice aktiv auf Port `8503`.
- Read-only API für Home-Zusammenfassung, Räume, Historien, Wärmepumpe und Wetter
- `/health/live` für Prozessgesundheit
- `/health/ready` für Datenbank und Collector-Frische
- Pydantic-Schemas als öffentliche API-Verträge
- zunächst nur lokale Bind-Adresse `127.0.0.1`

Der aktuelle Prototyp stellt `/health/live`, `/health/ready`, `/api/v1/rooms` und `/api/v1/rooms/{room_name}/history` bereit. Er verwendet dieselbe operative SQLite-Datei nur lesend; Provider und Collector bleiben ausschließlich auf `8501`.

Ergebnis: alle Dashboard-Daten sind ohne Streamlit abrufbar.

### Phase 4: SvelteKit-Oberfläche

Vergleich und Dev-Erweiterung 2026-09-20:

- Wertegleichheit bestätigt: 14 Räume, Sollwerte, Feuchte, Ventilstellung, Durchschnittstemperatur und Wärmepumpen-Kernwerte stimmen zwischen `8503` und `8501` überein.
- Dev geprüft und ergänzt: Home, Raumvergleich, Raumbericht, Raumdetail mit Historie, 14 gemeinsame Temperaturdiagramme, Wärmepumpenstatus und 7-Tage-Wetterbericht.
- Raumbericht erweitert: bestehende Tabelle bleibt erhalten und wird durch Temperatur- und Feuchte-Spidercharts ergänzt.
- Wärmepumpenansicht erweitert: beide Schemata und 30 KPI-/Featurewerte aus dem gemeinsamen Produktionsberechnungspfad ergänzt.
- Der Dev-Launcher weist Collector auf Nicht-Produktionsports ab und verhindert per `flock` einen zweiten Collector-Satz.
- Die Dev-Zeitdiagramme bieten gemeinsame Schalter für Ist, Ziel, Feuchte und Ventil; der Wärmepumpenbericht enthält zusätzlich Heizkurve und technischen Rohdaten-Explorer.
- Der produktive Streamlit-Fallback bleibt bis zur Abnahme der erweiterten Messreihenauswahl aktiv.

Reihenfolge der Views:

1. Home und Raumstatus
2. Raumdetail und Historie
3. Alle Diagramme
4. Wärmepumpenstatus und Schema
5. Wetter
6. Einstellungen und read-only Inventory

Mobile Anforderungen:

- keine horizontale Überbreite
- sichtbare Datenfrische direkt am Messwert
- kompakte Kennzahlen ohne unnötige Leerflächen
- Karten mit stabilen Dimensionen
- Diagramme mit gemeinsamer Filterung
- Browser-Tests bei mindestens 320px, 390px, 768px und Desktopbreite

### Phase 5: Parallelbetrieb

Status: abgeschlossen; der produktive Dienst ist auf den Migrationsstack umgeschaltet.

- produktive Migration-API/UI auf `8501` aktiv halten
- Streamlit nur noch als archivierten Rollback-Fallback verwenden
- neuen Migrationstestserver ausschließlich auf `8503` starten
- `8503` zunächst als reine Test-UI ohne Homematic-/Viessmann-Collector betreiben
- bis zur Abnahme darf nur `8501` Provider abfragen und die operative Datenbank aktualisieren
- FastAPI und SvelteKit über einen lokalen Reverse Proxy bündeln
- Streamlit bleibt über Port `8501` als produktiver Fallback verfügbar
- Homematic- und Viessmann-Collector werden genau einmal betrieben
- Vergleichstests zwischen Streamlit- und neuer UI durchführen

Start des aktuellen Testmodus ohne doppelte Datenabfragen:

```bash
HOMEDASH_PORT=8503 HOMEDASH_RUN_COLLECTORS=0 sh scripts/run_dashboard.sh
```

Der Testserver darf die Produktionsdaten read-only lesen, aber keine Provider aufrufen und keine Collector-Prozesse starten. Vor dem Umschalten müssen API und neue UI ihre Daten ebenfalls über den produktiven Datenpfad beziehen.

Abnahmekriterien:

- gleiche Raumwerte und Historien
- gleiche Viessmann-Messwerte mit sichtbarer Quellenzeit
- keine zusätzlichen Provider-Aufrufe durch die UI
- keine Regression bei Tailscale Serve
- mobile und Desktop-Browser-Smoke-Tests grün

### Phase 6: Umschalten und Aufräumen

Status: Umschaltung abgeschlossen am 2026-09-20.

- neuen Stack als `homedash.service` produktiv schalten
- Tailscale Serve auf den neuen lokalen Backend-/Proxy-Port zeigen lassen
- Streamlit als deaktivierbaren Fallback behalten
- mindestens eine Betriebsperiode beobachten
- erst danach Streamlit-Code und alte Service-Konfiguration entfernen
- Migration dokumentieren und Release taggen

Swap-Runbook:

1. `python scripts/backup_database.py --verify` ausführen.
2. Streamlit-Service und Datenbankbackup archivieren; `v0.9a` bleibt Rollback-Basis.
3. `homedash.service` auf `scripts/run_migration_prod.sh` umstellen.
4. Service neu starten und genau einen Homematic- sowie einen Viessmann-Collector prüfen.
5. Health, Home, Raumberichte, Diagramme, Wärmepumpenschemata, Heizkurve und Wetter prüfen.
6. Tailscale Serve auf `8501` prüfen.
7. Bei Fehlern Migration-Service stoppen und den archivierten Streamlit-Fallback auf `8501` starten.

## Deployment-Ziel

```text
systemd homedash-api.service       -> FastAPI auf 127.0.0.1:8000
systemd homedash-collector.service -> Homematic und Viessmann Jobs
systemd homedash-web.service       -> SvelteKit oder statische Auslieferung
Tailscale Serve                    -> lokaler Web-Port
```

Betriebsports:

- `8501`: produktive Streamlit-App, einzige aktive Datenabfrage und Datenbankaktualisierung
- `8503`: Migrationstestserver, read-only, keine Collector und keine Provider-Abfragen
- `8502`: frei für temporäre lokale Diagnose, nicht für den regulären Migrationstest

Der öffentliche Router bleibt ohne Portfreigabe. Tailscale ist der einzige externe Zugang.

## Datenmigration

Die vorhandene SQLite-Datei wird nicht automatisch verändert. Vor jeder Schemaänderung:

```bash
python scripts/backup_database.py --verify
```

Danach:

1. Datenbank kopieren.
2. Alembic-Migration auf der Kopie ausführen.
3. Zählungen und Zeitbereiche vergleichen.
4. Stichproben für Räume und Viessmann-Sensoren prüfen.
5. Erst danach den neuen Dienst auf die migrierte Datei zeigen lassen.

Alte Tabellen bleiben zunächst lesbar. Eine Löschung oder Umbenennung erfolgt erst nach einem bestätigten Release.

## Rollback

Bei Problemen:

1. Neuen Web-/API-Service stoppen.
2. Tailscale Serve auf den Streamlit-Port zurückstellen.
3. `v0.9a` oder den letzten bestätigten Streamlit-Commit auschecken.
4. Bestehende Datenbank beziehungsweise Backup weiterverwenden.
5. Fehler anhand von Collector- und API-Logs analysieren.

## Definition of Done

Die Migration ist abgeschlossen, wenn:

- alle produktiven Views im neuen Frontend verfügbar sind
- Provider- und API-Contract-Tests grün sind
- Datenbankmigration und Restore getestet sind
- mobile Browser-Tests ohne Overflow grün sind
- Healthchecks und Logs im Betrieb nutzbar sind
- Tailscale-Zugriff weiterhin funktioniert
- ein neuer Release-Tag mit Rollback-Anleitung veröffentlicht ist
- Streamlit mindestens eine vollständige Betriebsperiode erfolgreich als Fallback ersetzt hat
