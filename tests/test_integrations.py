from datetime import datetime, timezone

from src.database import get_latest_data_timestamps
from src.monitoring import build_system_alerts
from src.weather import fetch_forecast


def test_weather_contract_returns_seven_days() -> None:
    forecast = fetch_forecast()
    daily = forecast["daily"]
    assert len(daily["time"]) == 7
    assert len(daily["weather_code"]) == 7
    assert len(daily["temperature_2m_max"]) == 7
    assert len(daily["temperature_2m_min"]) == 7


def test_database_contract_returns_known_data() -> None:
    timestamps = get_latest_data_timestamps("data/heating_data.db")
    assert timestamps["homematic"]
    assert timestamps["viessmann"]


def test_alert_contract_accepts_current_data() -> None:
    alerts = build_system_alerts(
        [],
        {"homematic": "2026-09-19T12:00:00+00:00", "viessmann": "2026-09-19T12:00:00+00:00"},
        None,
        now=datetime(2026, 9, 19, 12, 10, tzinfo=timezone.utc),
    )
    assert alerts == []
