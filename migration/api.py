from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from fastapi.staticfiles import StaticFiles

from src.models import HeatPumpSnapshot
from src.monitoring import build_heat_pump_metrics
from src.viessmann_heatpump import feature_values, system_map


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


class HeatPumpResponse(BaseModel):
    model: str
    online: bool
    operating_mode: str | None = None
    compressor_active: bool | None = None
    floor_supply_celsius: float | None = None
    buffer_celsius: float | None = None
    produced_energy_today_kwh: float


class AlertResponse(BaseModel):
    severity: str
    title: str
    detail: str


class StatusResponse(BaseModel):
    alerts: list[AlertResponse]
    latest_homematic: str | None = None
    latest_viessmann: str | None = None


class HistoryPointResponse(BaseModel):
    recorded_at: str
    current_temperature: float
    target_temperature: float
    humidity: float
    valve_position: float


class HomeResponse(BaseModel):
    rooms: list[RoomReadingResponse]
    room_count: int
    open_valves: int
    average_temperature: float | None
    latest_homematic: str | None = None
    latest_viessmann: str | None = None
    heat_pump: HeatPumpResponse | None = None


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


def _feature_value(features: dict[str, Any], feature_name: str, property_name: str) -> Any:
    for feature in features.get("data", []):
        if not isinstance(feature, dict) or feature.get("feature") != feature_name:
            continue
        property_data = feature.get("properties", {}).get(property_name, {})
        if isinstance(property_data, dict):
            value = property_data.get("value")
            return value.get("value") if isinstance(value, dict) and "value" in value else value
        return property_data
    return None


def _latest_heat_pump(connection: sqlite3.Connection) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT model, online, features_json
        FROM viessmann_snapshots
        WHERE lower(model) LIKE '%vitocal%' OR lower(model) LIKE '%heatpump%'
        ORDER BY recorded_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    features = json.loads(row["features_json"])
    return {
        "model": row["model"],
        "online": bool(row["online"]),
        "operating_mode": _feature_value(features, "heating.secondaryCircuit.operation.state", "currentValue"),
        "compressor_active": _feature_value(features, "heating.compressors.0", "active"),
        "floor_supply_celsius": _feature_value(features, "heating.circuits.0.sensors.temperature.supply", "value"),
        "buffer_celsius": _feature_value(features, "heating.bufferCylinder.sensors.temperature.main", "value"),
        "produced_energy_today_kwh": sum(
            float(_feature_value(features, feature, "currentDay") or 0)
            for feature in (
                "heating.heat.production.summary.heating",
                "heating.heat.production.summary.dhw",
            )
        ),
    }


def _freshness_alerts(
    latest_homematic: str | None,
    latest_viessmann: str | None,
) -> list[AlertResponse]:
    now = datetime.now(timezone.utc)
    alerts: list[AlertResponse] = []
    for label, timestamp, limit_minutes in (
        ("Homematic", latest_homematic, 30),
        ("Viessmann", latest_viessmann, 60),
    ):
        if timestamp is None:
            alerts.append(AlertResponse(severity="warning", title=f"{label}-Daten fehlen", detail="Es wurde noch kein Snapshot gespeichert."))
            continue
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        age_minutes = (now - parsed).total_seconds() / 60
        if age_minutes > limit_minutes:
            alerts.append(AlertResponse(severity="warning", title=f"{label}-Daten veraltet", detail=f"Letzter Snapshot vor {age_minutes:.0f} Minuten."))
    return alerts


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


@app.get("/api/v1/home", response_model=HomeResponse)
def home() -> HomeResponse:
    try:
        with _connect_read_only() as connection:
            raw_rooms = _latest_rooms(connection)
            latest_homematic, latest_viessmann = _latest_timestamps(connection)
            raw_heat_pump = _latest_heat_pump(connection)
    except (FileNotFoundError, sqlite3.Error) as error:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {error}") from error
    rooms = [RoomReadingResponse(**room) for room in raw_rooms]
    return HomeResponse(
        rooms=rooms,
        room_count=len(rooms),
        open_valves=sum(room.valve_position > 0 for room in rooms),
        average_temperature=(sum(room.current_temperature for room in rooms) / len(rooms)) if rooms else None,
        latest_homematic=latest_homematic,
        latest_viessmann=latest_viessmann,
        heat_pump=HeatPumpResponse(**raw_heat_pump) if raw_heat_pump else None,
    )


@app.get("/api/v1/status", response_model=StatusResponse)
def status() -> StatusResponse:
    try:
        with _connect_read_only() as connection:
            latest_homematic, latest_viessmann = _latest_timestamps(connection)
    except (FileNotFoundError, sqlite3.Error) as error:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {error}") from error
    return StatusResponse(
        alerts=_freshness_alerts(latest_homematic, latest_viessmann),
        latest_homematic=latest_homematic,
        latest_viessmann=latest_viessmann,
    )


@app.get("/api/v1/heat-pump", response_model=HeatPumpResponse | None)
def heat_pump() -> HeatPumpResponse | None:
    try:
        with _connect_read_only() as connection:
            raw_heat_pump = _latest_heat_pump(connection)
    except (FileNotFoundError, sqlite3.Error) as error:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {error}") from error
    return HeatPumpResponse(**raw_heat_pump) if raw_heat_pump else None


@app.get("/api/v1/heat-pump/report")
def heat_pump_report() -> dict[str, Any] | None:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    try:
        with _connect_read_only() as connection:
            latest_row = connection.execute(
                """
                SELECT device_id, model, online, features_json, recorded_at
                FROM viessmann_snapshots
                WHERE lower(model) LIKE '%vitocal%' OR lower(model) LIKE '%heatpump%'
                ORDER BY recorded_at DESC
                LIMIT 1
                """
            ).fetchone()
            if latest_row is None:
                return None
            history_rows = connection.execute(
                """
                SELECT recorded_at, features_json
                FROM viessmann_snapshots
                WHERE recorded_at >= ?
                  AND (lower(model) LIKE '%vitocal%' OR lower(model) LIKE '%heatpump%')
                ORDER BY recorded_at
                """,
                (cutoff,),
            ).fetchall()
    except (FileNotFoundError, sqlite3.Error) as error:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {error}") from error

    snapshot = HeatPumpSnapshot(
        device_id=latest_row["device_id"],
        model=latest_row["model"],
        online=bool(latest_row["online"]),
        features=json.loads(latest_row["features_json"]),
    )
    history = [
        {"recorded_at": row["recorded_at"], "features": json.loads(row["features_json"])}
        for row in history_rows
    ]
    return {
        "model": snapshot.model,
        "device_id": snapshot.device_id,
        "online": snapshot.online,
        "recorded_at": latest_row["recorded_at"],
        "metrics": asdict(build_heat_pump_metrics(snapshot, history)),
        "features": feature_values(snapshot),
        "system_map": system_map(snapshot),
        "feature_timestamps": {
            str(item.get("feature")): str(item.get("timestamp"))
            for item in snapshot.features.get("data", [])
            if isinstance(item, dict) and item.get("timestamp")
        },
    }


@app.get("/api/v1/weather")
def weather() -> dict[str, Any]:
    from src.weather import LOCATION_NAME, fetch_forecast

    forecast = fetch_forecast()
    return {"location": LOCATION_NAME, "daily": forecast["daily"]}


@app.get("/api/v1/rooms/{room_name}/history", response_model=list[HistoryPointResponse])
def room_history(
    room_name: str,
    hours: int = Query(default=24, ge=1, le=720),
) -> list[HistoryPointResponse]:
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
    return [HistoryPointResponse(**dict(row)) for row in rows]


app.mount("/", StaticFiles(directory=Path(__file__).with_name("web"), html=True), name="migration-web")
