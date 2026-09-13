import json
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


def save_home_snapshot(database_path: Union[str, Path], home: Home, recorded_at: Optional[datetime] = None) -> int:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    initialize_history(path)
    rows = snapshot_home(home, recorded_at)
    with sqlite3.connect(path) as connection:
        connection.executemany(
            """
            INSERT INTO homematic_snapshots (
                recorded_at, object_type, object_id, label,
                model_type, channel_type, values_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)
