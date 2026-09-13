import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Union

from src.models import RoomReading
from src.history import initialize_history
from src.room_layout import ROOM_ALIASES, ROOM_LEVELS, UNASSIGNED


def backup_database(database_path: Union[str, Path], backup_path: Union[str, Path]) -> Path:
    """Create a consistent SQLite backup without modifying the source database."""
    source = Path(database_path)
    destination = Path(backup_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_connection:
        with sqlite3.connect(destination) as backup_connection:
            source_connection.backup(backup_connection)
    return destination


def save_viessmann_snapshots(database_path: Union[str, Path], inventory: list[dict[str, object]]) -> int:
    initialize_database(database_path)
    recorded_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            "INSERT INTO viessmann_snapshots (recorded_at, device_id, model, online, features_json) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    recorded_at,
                    str(device["id"]),
                    str(device["model"]),
                    int(bool(device["online"])),
                    json.dumps(device["features"], ensure_ascii=False, sort_keys=True, default=str),
                )
                for device in inventory
            ],
        )
    return len(inventory)


SCHEMA = """
CREATE TABLE IF NOT EXISTS room_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_name TEXT NOT NULL,
    current_temperature REAL NOT NULL,
    target_temperature REAL NOT NULL,
    humidity REAL NOT NULL,
    valve_position REAL NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_room_readings_room_time
    ON room_readings (room_name, recorded_at DESC);
CREATE TABLE IF NOT EXISTS target_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_name TEXT NOT NULL,
    target_temperature REAL NOT NULL,
    changed_at TEXT NOT NULL,
    source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS room_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    value REAL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_room_events_room_time
    ON room_events (room_name, recorded_at DESC);
CREATE TABLE IF NOT EXISTS viessmann_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TEXT NOT NULL,
    device_id TEXT NOT NULL,
    model TEXT NOT NULL,
    online INTEGER NOT NULL,
    features_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_viessmann_snapshots_time
    ON viessmann_snapshots (recorded_at DESC);
"""


def initialize_database(database_path: Union[str, Path]) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(room_readings)")}
        if "level" not in columns:
            connection.execute(
                f"ALTER TABLE room_readings ADD COLUMN level TEXT NOT NULL DEFAULT '{UNASSIGNED}'"
            )
        connection.execute("UPDATE room_readings SET room_name = TRIM(room_name)")
        for alias, canonical_name in ROOM_ALIASES.items():
            connection.execute(
                "UPDATE room_readings SET room_name = ? WHERE room_name = ?",
                (canonical_name, alias),
            )
        for room_name, level in ROOM_LEVELS.items():
            connection.execute(
                "UPDATE room_readings SET level = ? WHERE room_name = ?",
                (level, room_name),
            )
    initialize_history(path)


def save_readings(database_path: Union[str, Path], readings: list[RoomReading]) -> None:
    initialize_database(database_path)
    event_rows = []
    with sqlite3.connect(database_path) as connection:
        for reading in readings:
            previous = connection.execute(
                "SELECT target_temperature, valve_position FROM room_readings WHERE room_name = ? ORDER BY recorded_at DESC, id DESC LIMIT 1",
                (reading.room_name,),
            ).fetchone()
            if previous:
                previous_target, previous_valve = previous
                if round(previous_target, 1) != round(reading.target_temperature, 1):
                    event_rows.append((reading.room_name, "target_changed", f"Target changed to {reading.target_temperature:.1f} C", reading.target_temperature, reading.recorded_at.isoformat()))
                if previous_valve <= 0 < reading.valve_position:
                    event_rows.append((reading.room_name, "valve_opened", "Valve opened", reading.valve_position, reading.recorded_at.isoformat()))
                elif previous_valve > 0 >= reading.valve_position:
                    event_rows.append((reading.room_name, "valve_closed", "Valve closed", reading.valve_position, reading.recorded_at.isoformat()))
        if event_rows:
            connection.executemany(
                "INSERT INTO room_events (room_name, event_type, message, value, recorded_at) VALUES (?, ?, ?, ?, ?)",
                event_rows,
            )
    rows = [
        (
            reading.room_name,
            reading.current_temperature,
            reading.target_temperature,
            reading.humidity,
            reading.valve_position,
            reading.recorded_at.isoformat(),
            reading.level,
        )
        for reading in readings
    ]
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO room_readings (
                room_name,
                current_temperature,
                target_temperature,
                humidity,
                valve_position,
                recorded_at,
                level
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def get_room_events(database_path: Union[str, Path], room_name: str, limit: int = 50) -> list[dict[str, object]]:
    initialize_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT event_type, message, value, recorded_at FROM room_events WHERE room_name = ? ORDER BY recorded_at DESC, id DESC LIMIT ?",
            (room_name, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_latest_readings(database_path: Union[str, Path]) -> list[dict[str, object]]:
    initialize_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT room_name, current_temperature, target_temperature,
                   humidity, valve_position, recorded_at, level
            FROM (
                SELECT room_name, current_temperature, target_temperature,
                       humidity, valve_position, recorded_at, level,
                       ROW_NUMBER() OVER (
                           PARTITION BY room_name
                           ORDER BY recorded_at DESC, id DESC
                       ) AS row_number
                FROM room_readings
            ) AS latest
            WHERE row_number = 1
            ORDER BY room_name
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_room_trends(database_path: Union[str, Path], room_name: str) -> dict[str, str]:
    """Return direction markers for the latest room temperature and humidity."""
    initialize_database(database_path)
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT current_temperature, humidity
            FROM room_readings
            WHERE room_name = ?
            ORDER BY recorded_at DESC, id DESC
            LIMIT 24
            """,
            (room_name,),
        ).fetchall()

    if len(rows) < 2:
        return {"temperature": "->", "humidity": "->"}

    current = rows[0]

    def previous_distinct(index: int) -> Optional[float]:
        current_value = current[index]
        for row in rows[1:]:
            if round(row[index], 1) != round(current_value, 1):
                return row[index]
        return None

    def direction(current_value: float, previous_value: float, quarter: float, full: float) -> str:
        change = current_value - previous_value
        if change >= full:
            return "↑"
        if change >= quarter:
            return "↗"
        if change <= -full:
            return "↓"
        if change <= -quarter:
            return "↘"
        return "→"

    return {
        "temperature": direction(current[0], previous_distinct(0) or current[0], quarter=0.1, full=0.5),
        "humidity": direction(current[1], previous_distinct(1) or current[1], quarter=1.0, full=5.0),
    }


def get_room_history(
    database_path: Union[str, Path],
    room_name: str,
    hours: int,
) -> list[dict[str, object]]:
    if hours <= 0:
        raise ValueError("hours must be greater than zero")

    initialize_database(database_path)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT recorded_at, current_temperature, target_temperature,
                   humidity, valve_position
            FROM room_readings
            WHERE room_name = ? AND recorded_at >= ?
            ORDER BY recorded_at
            """,
            (room_name, cutoff.isoformat()),
        ).fetchall()
    return [dict(row) for row in rows]


def record_target_change(
    database_path: Union[str, Path],
    room_name: str,
    target_temperature: float,
    source: str = "dashboard",
) -> None:
    initialize_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO target_changes (room_name, target_temperature, changed_at, source) VALUES (?, ?, datetime('now'), ?)",
            (room_name, target_temperature, source),
        )
