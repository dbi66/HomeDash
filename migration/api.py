from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict


DATABASE_PATH = Path(os.getenv("HOMEDASH_DATABASE", "data/heating_data.db"))

app = FastAPI(
    title="HomeDash Migration API",
    version="0.10.0-dev",
    description="Read-only API for the HomeDash migration prototype.",
)


class RoomReadingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    room_name: str
    current_temperature: float
    target_temperature: float
    humidity: float
    valve_position: float
    recorded_at: str
    level: str


class HealthResponse(BaseModel):
    status: str
    database: str
    latest_homematic: str | None = None
    latest_viessmann: str | None = None


def _database_path() -> Path:
    return Path(os.getenv("HOMEDASH_DATABASE", str(DATABASE_PATH))).resolve()


def _connect_read_only() -> sqlite3.Connection:
    database_path = _database_path()
    if not database_path.exists():
        raise FileNotFoundError(database_path)
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _latest_timestamps(connection: sqlite3.Connection) -> tuple[str | None, str | None]:
    room_timestamp = connection.execute("SELECT MAX(recorded_at) FROM room_readings").fetchone()[0]
    viessmann_timestamp = connection.execute("SELECT MAX(recorded_at) FROM viessmann_snapshots").fetchone()[0]
    return room_timestamp, viessmann_timestamp


def _latest_rooms(connection: sqlite3.Connection) -> list[dict[str, Any]]:
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


@app.get("/health/live", response_model=HealthResponse)
def live_health() -> HealthResponse:
    return HealthResponse(status="ok", database="read-only")


@app.get("/health/ready", response_model=HealthResponse)
def ready_health() -> HealthResponse:
    try:
        with _connect_read_only() as connection:
            latest_homematic, latest_viessmann = _latest_timestamps(connection)
    except (FileNotFoundError, sqlite3.Error) as error:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {error}") from error
    return HealthResponse(
        status="ready",
        database="read-only",
        latest_homematic=latest_homematic,
        latest_viessmann=latest_viessmann,
    )


@app.get("/api/v1/rooms", response_model=list[RoomReadingResponse])
def rooms() -> list[RoomReadingResponse]:
    try:
        with _connect_read_only() as connection:
            return [RoomReadingResponse(**row) for row in _latest_rooms(connection)]
    except (FileNotFoundError, sqlite3.Error) as error:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {error}") from error


@app.get("/api/v1/rooms/{room_name}/history", response_model=list[dict[str, Any]])
def room_history(
    room_name: str,
    hours: int = Query(default=24, ge=1, le=720),
) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        with _connect_read_only() as connection:
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
    except (FileNotFoundError, sqlite3.Error) as error:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {error}") from error
    return [dict(row) for row in rows]
