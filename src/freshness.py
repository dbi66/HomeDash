from __future__ import annotations

from datetime import datetime


def parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.astimezone()
    return timestamp


def age_minutes(value: object, now: datetime | None = None) -> int | None:
    timestamp = parse_timestamp(value)
    if timestamp is None:
        return None
    current_time = now or datetime.now(timestamp.tzinfo)
    return max(0, int((current_time - timestamp).total_seconds() / 60))


def status(value: object, expected_interval_minutes: int, now: datetime | None = None) -> str:
    age = age_minutes(value, now)
    if age is None:
        return "keine Daten"
    if age <= expected_interval_minutes * 2:
        return "aktuell"
    return "veraltet"
