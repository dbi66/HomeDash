import sqlite3
from pathlib import Path
from typing import Union

from src.models import RoomReading
from src.room_layout import ROOM_ALIASES, ROOM_LEVELS, UNASSIGNED


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


def save_readings(database_path: Union[str, Path], readings: list[RoomReading]) -> None:
    initialize_database(database_path)
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
