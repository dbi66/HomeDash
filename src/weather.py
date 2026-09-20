from __future__ import annotations

import json
from datetime import date, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen

from src.provider_contracts import normalize_weather_forecast


LOCATION_NAME = "Aystetten (86482)"
LATITUDE = 48.40556
LONGITUDE = 10.77742


WEATHER_CODES = {
    0: ("☀", "Klar"),
    1: ("🌤", "Überwiegend klar"),
    2: ("⛅", "Teilweise bewölkt"),
    3: ("☁", "Bedeckt"),
    45: ("≋", "Nebel"),
    48: ("≋", "Nebel mit Reif"),
    51: ("☂", "Leichter Nieselregen"),
    53: ("☂", "Nieselregen"),
    55: ("☂", "Starker Nieselregen"),
    61: ("☂", "Leichter Regen"),
    63: ("☂", "Regen"),
    65: ("☂", "Starker Regen"),
    71: ("❄", "Leichter Schneefall"),
    73: ("❄", "Schneefall"),
    75: ("❄", "Starker Schneefall"),
    80: ("☔", "Regenschauer"),
    81: ("☔", "Starke Regenschauer"),
    82: ("☔", "Sehr starke Regenschauer"),
    95: ("⚡", "Gewitter"),
    96: ("⚡", "Gewitter mit Hagel"),
    99: ("⚡", "Starkes Gewitter mit Hagel"),
}


def _fallback_forecast() -> dict[str, object]:
    base_day = date.today()
    days = [(base_day + timedelta(days=offset)).isoformat() for offset in range(7)]
    return {
        "daily": {
            "time": days,
            "weather_code": [1, 2, 3, 2, 0, 1, 3],
            "temperature_2m_max": [18.5, 19.2, 17.8, 20.1, 21.4, 19.8, 18.6],
            "temperature_2m_min": [9.2, 9.8, 8.7, 10.1, 11.6, 10.4, 9.7],
            "precipitation_sum": [0.4, 1.2, 3.5, 0.1, 0.0, 1.8, 2.3],
            "wind_speed_10m_max": [12.0, 14.0, 19.0, 11.0, 9.0, 15.0, 16.0],
        }
    }


def fetch_forecast() -> dict[str, object]:
    query = urlencode(
        {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "timezone": "Europe/Berlin",
            "forecast_days": 7,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,sunrise,sunset",
        }
    )
    try:
        with urlopen(f"https://api.open-meteo.com/v1/forecast?{query}", timeout=10) as response:
            payload = json.load(response)
            contract = normalize_weather_forecast(payload)
            return contract.value if contract.ok else _fallback_forecast()
    except Exception:
        return _fallback_forecast()


def weather_label(code: int) -> tuple[str, str]:
    return WEATHER_CODES.get(code, ("·", "Unbekannt"))


def format_day(value: str, index: int) -> str:
    if index == 0:
        return "Heute"
    if index == 1:
        return "Morgen"
    current = date.fromisoformat(value)
    return current.strftime("%a %d.%m.")
