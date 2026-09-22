from __future__ import annotations

from html import escape

import streamlit as st

from src.config import DATABASE_PATH
from src.database import get_latest_viessmann_snapshots
from src.feature_access import FeatureAccessor
from src.viessmann_heatpump import heat_pump_snapshots_from_inventory
from src.weather import LOCATION_NAME, fetch_forecast, format_day, weather_label


def render_today_weather_chart(hourly: dict[str, object], today: str) -> None:
    times = hourly.get("time", [])
    temperatures = hourly.get("temperature_2m", [])
    apparent = hourly.get("apparent_temperature", [])
    rain = hourly.get("precipitation_probability", [])
    wind = hourly.get("wind_speed_10m", [])
    points = [
        {
            "time": str(times[index]),
            "temperature": float(temperatures[index]),
            "apparent": float(apparent[index]),
            "rain": float(rain[index] or 0),
            "wind": float(wind[index] or 0),
        }
        for index in range(min(len(times), len(temperatures), len(apparent), len(rain), len(wind)))
        if str(times[index]).startswith(today)
    ]
    if len(points) < 2:
        st.info("Kein stündlicher Wetterverlauf verfügbar.")
        return
    width, height, left, right, top, bottom = 900, 300, 44, 44, 28, 42
    temperatures = [value for point in points for value in (point["temperature"], point["apparent"])]
    minimum = int(min(temperatures) - 1)
    maximum = int(max(temperatures) + 1)
    wind_maximum = max(20.0, max(point["wind"] for point in points))

    def x(index: int) -> float:
        return left + index * (width - left - right) / max(1, len(points) - 1)

    def y_temperature(value: float) -> float:
        return height - bottom - (value - minimum) * (height - top - bottom) / max(1, maximum - minimum)

    def y_percent(value: float) -> float:
        return height - bottom - value * (height - top - bottom) / 100

    def y_wind(value: float) -> float:
        return height - bottom - value * (height - top - bottom) / wind_maximum

    def line(key: str, color: str, scale, dash: str = "") -> str:
        points_text = " ".join(f"{x(index):.1f},{scale(point[key]):.1f}" for index, point in enumerate(points))
        dash_attribute = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline fill="none" stroke="{color}" stroke-width="3"{dash_attribute} points="{points_text}"/>'

    grid = "".join(
        f'<line x1="{left}" y1="{y_temperature(value):.1f}" x2="{width - right}" y2="{y_temperature(value):.1f}" stroke="#e6edf3"/><text x="{left - 7}" y="{y_temperature(value) + 4:.1f}" text-anchor="end" fill="#627d98" font-size="11">{value}°</text>'
        for value in (minimum, (minimum + maximum) // 2, maximum)
    )
    bars = "".join(
        f'<rect x="{x(index) - 5:.1f}" y="{y_percent(point["rain"]):.1f}" width="10" height="{height - bottom - y_percent(point["rain"]):.1f}" rx="3" fill="#8fc6e8" opacity=".55"/>'
        for index, point in enumerate(points)
    )
    labels = "".join(
        f'<text x="{x(index):.1f}" y="{height - 16}" text-anchor="middle" fill="#627d98" font-size="10">{escape(point["time"][11:16])}</text>'
        for index, point in enumerate(points) if index % 3 == 0
    )
    chart = f'''<div class="forecast-chart-wrap"><svg viewBox="0 0 {width} {height}" role="img" aria-label="Stündlicher Wetterverlauf für heute">{grid}{bars}<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="#9fb3c8"/>{line("temperature", "#c2410c", y_temperature)}{line("apparent", "#64748b", y_temperature, "7 5")}{line("wind", "#2f855a", y_wind, "3 4")}{labels}<text x="{left}" y="15" fill="#52606d" font-size="11" font-weight="700">Temperatur °C</text><text x="{width - right}" y="15" text-anchor="end" fill="#52606d" font-size="11" font-weight="700">Regenbalken = Wahrscheinlichkeit · Wind gestrichelt</text></svg><div class="forecast-chart-legend"><span class="forecast-chart-legend__temp">Ist-Temperatur</span><span class="forecast-chart-legend__apparent">Gefühlt</span><span class="forecast-chart-legend__wind">Wind km/h</span><span class="forecast-chart-legend__rain">Regen %</span></div></div>'''
    st.markdown(chart, unsafe_allow_html=True)


def render_weather_report() -> None:
    st.markdown('<div class="level-heading">7-Tage-Wetterbericht</div>', unsafe_allow_html=True)
    st.caption(f"{LOCATION_NAME} | Vorhersage von Open-Meteo | Aktualisierung beim Öffnen")
    try:
        forecast = fetch_forecast()
    except Exception as error:
        st.error(f"Wetterdaten konnten nicht geladen werden: {error}")
        return
    daily = forecast.get("daily", {})
    current = forecast.get("current", {})
    current_icon, current_condition = weather_label(int(current.get("weather_code", 0)))
    heat_pumps = heat_pump_snapshots_from_inventory(get_latest_viessmann_snapshots(DATABASE_PATH))
    viessmann_outside = None
    if heat_pumps:
        value = FeatureAccessor(heat_pumps[0].features).value("heating.sensors.temperature.outside", "value")
        viessmann_outside = float(value) if isinstance(value, (int, float)) else None
    st.markdown(
        f'<div class="weather-current"><div><strong>Aktuell:</strong> {current_icon} {escape(current_condition)} · {current.get("temperature_2m", "n/a")} °C</div><div>Feuchte {current.get("relative_humidity_2m", "n/a")} % · Wind {current.get("wind_speed_10m", "n/a")} km/h · Viessmann außen {viessmann_outside if viessmann_outside is not None else "n/a"} °C</div></div>',
        unsafe_allow_html=True,
    )
    dates = daily.get("time", [])
    codes = daily.get("weather_code", [])
    maximums = daily.get("temperature_2m_max", [])
    minimums = daily.get("temperature_2m_min", [])
    precipitation = daily.get("precipitation_sum", [])
    winds = daily.get("wind_speed_10m_max", [])
    render_today_weather_chart(forecast.get("hourly", {}), str(dates[0]) if dates else "")
    minimum = min(float(value) for value in minimums[:7])
    maximum = max(float(value) for value in maximums[:7])
    temperature_span = max(1.0, maximum - minimum)
    cards = []
    for index, forecast_date in enumerate(dates[:7]):
        icon, condition = weather_label(int(codes[index]))
        low = float(minimums[index])
        high = float(maximums[index])
        left = (low - minimum) / temperature_span * 100
        width = max(5.0, (high - low) / temperature_span * 100)
        cards.append(
            f'<article class="weather-card{" weather-card--today" if index == 0 else ""}">'
            f'<div class="weather-card__head"><div class="weather-card__day">{escape(format_day(forecast_date, index))}</div><div class="weather-card__icon">{icon}</div></div>'
            f'<div class="weather-card__condition">{escape(condition)}</div>'
            f'<div class="weather-card__temps"><strong>{high:.0f}°</strong><span>{low:.0f}°</span></div>'
            f'<div class="weather-card__range"><span style="left:{left:.1f}%;width:{width:.1f}%"></span></div>'
            f'<div class="weather-card__meta">Regen {float(precipitation[index]):.1f} mm<br>'
            f'Wind bis {float(winds[index]):.0f} km/h</div>'
            f'</article>'
        )
    st.markdown(f'<div class="weather-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
