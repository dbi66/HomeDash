import json
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from homematicip.home import Home


HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS homematic_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    label TEXT NOT NULL,
    model_type TEXT,
    channel_type TEXT,
    values_json TEXT NOT NULL
    ,snapshot_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_homematic_snapshots_time
    ON homematic_snapshots (recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_homematic_snapshots_object
    ON homematic_snapshots (object_id, recorded_at DESC);
"""

SKIP_ATTRIBUTES = {
    "id",
    "homeId",
    "device",
    "groups",
    "functionalChannels",
    "_connection",
    "_rawJSONData",
}


def initialize_history(database_path: Union[str, Path]) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.executescript(HISTORY_SCHEMA)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(homematic_snapshots)")}
        if "snapshot_hash" not in columns:
            connection.execute("ALTER TABLE homematic_snapshots ADD COLUMN snapshot_hash TEXT")


def _json_value(value: Any) -> Optional[Any]:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None


def scalar_attributes(value: object) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    for name in sorted(dir(value)):
        if name.startswith("_") or name in SKIP_ATTRIBUTES:
            continue
        try:
            attribute = _json_value(getattr(value, name))
        except Exception:
            continue
        if attribute is not None:
            attributes[name] = attribute
    return attributes


def _snapshot_row(
    recorded_at: datetime,
    object_type: str,
    value: object,
    object_id: str,
    label: str,
    model_type: str = "",
    channel_type: str = "",
) -> tuple[str, str, str, str, str, str, str]:
    return (
        recorded_at.isoformat(),
        object_type,
        object_id,
        label,
        model_type,
        channel_type,
        json.dumps(scalar_attributes(value), ensure_ascii=False, sort_keys=True),
    )


def snapshot_home(home: Home, recorded_at: Optional[datetime] = None) -> list[tuple[str, str, str, str, str, str, str]]:
    timestamp = recorded_at or datetime.now().astimezone()
    rows = []

    for device in home.devices:
        device_id = str(getattr(device, "id", ""))
        rows.append(
            _snapshot_row(
                timestamp,
                "device",
                device,
                device_id,
                str(getattr(device, "label", "")),
                str(getattr(device, "modelType", "")),
            )
        )
        for channel in getattr(device, "functionalChannels", []):
            channel_index = str(getattr(channel, "index", ""))
            rows.append(
                _snapshot_row(
                    timestamp,
                    "channel",
                    channel,
                    f"{device_id}:{channel_index}",
                    str(getattr(channel, "label", "")),
                    str(getattr(device, "modelType", "")),
                    str(getattr(channel, "functionalChannelType", "")),
                )
            )

    for group in home.groups:
        group_id = str(getattr(group, "id", ""))
        rows.append(
            _snapshot_row(
                timestamp,
                "group",
                group,
                group_id,
                str(getattr(group, "label", "")),
                channel_type=str(getattr(group, "groupType", "")),
            )
        )
    return rows


def save_home_snapshot(
    database_path: Union[str, Path],
    home: Home,
    recorded_at: Optional[datetime] = None,
    min_interval_minutes: int = 0,
) -> int:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    initialize_history(path)
    rows = snapshot_home(home, recorded_at)
    snapshot_hash = hashlib.sha256(
        json.dumps([row[1:] for row in rows], ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    with sqlite3.connect(path) as connection:
        previous = connection.execute(
            "SELECT snapshot_hash, recorded_at FROM homematic_snapshots ORDER BY recorded_at DESC LIMIT 1"
        ).fetchone()
        if previous:
            previous_hash, previous_timestamp = previous
            if previous_hash == snapshot_hash:
                return 0
            if min_interval_minutes > 0:
                previous_time = datetime.fromisoformat(previous_timestamp)
                current_time = datetime.fromisoformat(rows[0][0])
                elapsed_minutes = (current_time - previous_time).total_seconds() / 60
                if elapsed_minutes < min_interval_minutes:
                    return 0
        connection.executemany(
            """
            INSERT INTO homematic_snapshots (
                recorded_at, object_type, object_id, label,
                model_type, channel_type, values_json, snapshot_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [row + (snapshot_hash,) for row in rows],
        )
    return len(rows)
