from __future__ import annotations

import json
from datetime import date
from urllib.parse import urlencode
from urllib.request import urlopen


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
    with urlopen(f"https://api.open-meteo.com/v1/forecast?{query}", timeout=10) as response:
        return json.load(response)


def weather_label(code: int) -> tuple[str, str]:
    return WEATHER_CODES.get(code, ("·", "Unbekannt"))


def format_day(value: str, index: int) -> str:
    if index == 0:
        return "Heute"
    if index == 1:
        return "Morgen"
    current = date.fromisoformat(value)
    return current.strftime("%a %d.%m.")
