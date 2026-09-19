from datetime import datetime, timezone

from src.display import format_data_age, format_timestamp


def test_format_timestamp_uses_local_display_format() -> None:
    assert format_timestamp("2026-09-19T12:34:56+00:00") == "19.09.2026 14:34"


def test_format_data_age_reports_relative_age() -> None:
    now = datetime(2026, 9, 19, 14, 0, tzinfo=timezone.utc)
    assert format_data_age("2026-09-19T13:45:00+00:00", now) == "vor 15 min"
