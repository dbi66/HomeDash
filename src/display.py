from __future__ import annotations

from datetime import datetime


def parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.astimezone()
    return timestamp


def format_timestamp(value: object) -> str:
    timestamp = parse_timestamp(value)
    return "keine Daten" if timestamp is None else timestamp.astimezone().strftime("%d.%m.%Y %H:%M")


def format_data_age(value: object, now: datetime | None = None) -> str:
    timestamp = parse_timestamp(value)
    if timestamp is None:
        return "keine Daten"
    current_time = now or datetime.now(timestamp.tzinfo)
    minutes = max(0, int((current_time - timestamp).total_seconds() / 60))
    if minutes < 2:
        return "gerade eben"
    if minutes < 60:
        return f"vor {minutes} min"
    return f"vor {minutes // 60} h"
