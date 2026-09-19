from __future__ import annotations

from html import escape

import streamlit as st

from src.weather import LOCATION_NAME, fetch_forecast, format_day, weather_label


def render_weather_report() -> None:
    st.markdown('<div class="level-heading">7-Tage-Wetterbericht</div>', unsafe_allow_html=True)
    st.caption(f"{LOCATION_NAME} | Vorhersage von Open-Meteo | Aktualisierung beim Öffnen")
    try:
        forecast = fetch_forecast()
    except Exception as error:
        st.error(f"Wetterdaten konnten nicht geladen werden: {error}")
        return
    daily = forecast.get("daily", {})
    dates = daily.get("time", [])
    codes = daily.get("weather_code", [])
    maximums = daily.get("temperature_2m_max", [])
    minimums = daily.get("temperature_2m_min", [])
    precipitation = daily.get("precipitation_sum", [])
    winds = daily.get("wind_speed_10m_max", [])
    cards = []
    for index, forecast_date in enumerate(dates[:7]):
        icon, condition = weather_label(int(codes[index]))
        cards.append(
            f'<article class="weather-card">'
            f'<div class="weather-card__day">{escape(format_day(forecast_date, index))}</div>'
            f'<div class="weather-card__icon">{icon}</div>'
            f'<div class="weather-card__condition">{escape(condition)}</div>'
            f'<div class="weather-card__temps">{float(maximums[index]):.0f}° / {float(minimums[index]):.0f}°C</div>'
            f'<div class="weather-card__meta">Regen {float(precipitation[index]):.1f} mm<br>'
            f'Wind bis {float(winds[index]):.0f} km/h</div>'
            f'</article>'
        )
    st.markdown(f'<div class="weather-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
