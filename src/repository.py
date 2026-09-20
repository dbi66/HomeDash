from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from src.database import initialize_database


class MonitoringRepository:
    """Small read-side repository for monitoring queries."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        initialize_database(self.database_path)

    def latest_timestamps(self) -> dict[str, str | None]:
        with sqlite3.connect(self.database_path) as connection:
            room_timestamp = connection.execute("SELECT MAX(recorded_at) FROM room_readings").fetchone()[0]
            viessmann_timestamp = connection.execute("SELECT MAX(recorded_at) FROM viessmann_snapshots").fetchone()[0]
        return {"homematic": room_timestamp, "viessmann": viessmann_timestamp}

    def latest_room_readings(self) -> list[dict[str, object]]:
        with sqlite3.connect(self.database_path) as connection:
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

    def latest_viessmann(self) -> list[dict[str, object]]:
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            latest = connection.execute("SELECT MAX(recorded_at) FROM viessmann_snapshots").fetchone()[0]
            if latest is None:
                return []
            rows = connection.execute(
                "SELECT device_id, model, online, features_json FROM viessmann_snapshots WHERE recorded_at = ? ORDER BY model, device_id",
                (latest,),
            ).fetchall()
        return [
            {"id": row["device_id"], "model": row["model"], "online": bool(row["online"]), "features": json.loads(row["features_json"])}
            for row in rows
        ]

    def room_history(self, room_name: str, hours: int) -> list[dict[str, object]]:
        if hours <= 0:
            raise ValueError("hours must be greater than zero")
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with sqlite3.connect(self.database_path) as connection:
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

    def viessmann_features(self, hours: int = 24) -> list[dict[str, object]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT recorded_at, device_id, model, features_json FROM viessmann_snapshots WHERE recorded_at >= ? AND (lower(model) LIKE '%vitocal%' OR lower(model) LIKE '%heatpump%') ORDER BY recorded_at ASC",
                (cutoff,),
            ).fetchall()
        return [
            {"recorded_at": row["recorded_at"], "device_id": row["device_id"], "model": row["model"], "features": json.loads(row["features_json"])}
            for row in rows
        ]
