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

- Domänenmodelle für Raum, Sensor, Snapshot, Providerstatus und Messwert definieren
- `recorded_at` und `source_timestamp` getrennt speichern
- `quality` und `is_stale` für jeden externen Messwert vorsehen
- Provider-Adapter von UI und Repository entkoppeln
- Contract-Tests für Homematic, Viessmann und Wetter schreiben

Ergebnis: Backend-unabhängige, testbare Datenverträge.

### Phase 2: Collector und Persistenz

- Homematic-Collector als eigenständigen Prozess stabilisieren
- Viessmann-Collector als eigenständigen Prozess stabilisieren
- Retry, Backoff, Timeout und verständliche Fehlerzustände vereinheitlichen
- SQLite-WAL und Alembic einführen
- Aufbewahrungs- und Backup-Strategie dokumentieren
- `collection_runs` für Erfolg, Fehler, Laufzeit und Datenalter ergänzen

Ergebnis: zuverlässige Datenversorgung ohne Streamlit-Abhängigkeit.

### Phase 3: FastAPI-Backend

- Read-only API für Home-Zusammenfassung, Räume, Historien, Wärmepumpe und Wetter
- `/health/live` für Prozessgesundheit
- `/health/ready` für Datenbank und Collector-Frische
- Pydantic-Schemas als öffentliche API-Verträge
- zunächst nur lokale Bind-Adresse `127.0.0.1`

Ergebnis: alle Dashboard-Daten sind ohne Streamlit abrufbar.

### Phase 4: SvelteKit-Oberfläche

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

- neues Frontend zunächst unter einem separaten lokalen Port starten
- FastAPI und SvelteKit über einen lokalen Reverse Proxy bündeln
- Streamlit bleibt über Port `8501` als Fallback verfügbar
- Homematic- und Viessmann-Collector werden nur einmal betrieben
- Vergleichstests zwischen Streamlit- und neuer UI durchführen

Abnahmekriterien:

- gleiche Raumwerte und Historien
- gleiche Viessmann-Messwerte mit sichtbarer Quellenzeit
- keine zusätzlichen Provider-Aufrufe durch die UI
- keine Regression bei Tailscale Serve
- mobile und Desktop-Browser-Smoke-Tests grün

### Phase 6: Umschalten und Aufräumen

- neuen Stack als systemd-Service produktiv schalten
- Tailscale Serve auf den neuen lokalen Backend-/Proxy-Port zeigen lassen
- Streamlit als deaktivierbaren Fallback behalten
- mindestens eine Betriebsperiode beobachten
- erst danach Streamlit-Code und alte Service-Konfiguration entfernen
- Migration dokumentieren und Release taggen

## Deployment-Ziel

```text
systemd homedash-api.service       -> FastAPI auf 127.0.0.1:8000
systemd homedash-collector.service -> Homematic und Viessmann Jobs
systemd homedash-web.service       -> SvelteKit oder statische Auslieferung
Tailscale Serve                    -> lokaler Web-Port
```

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
