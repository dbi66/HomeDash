from __future__ import annotations

from datetime import datetime
from html import escape
import streamlit as st

from src.dashboard_views import render_overview
from src.database import get_latest_data_timestamps, get_latest_viessmann_snapshots, get_viessmann_feature_history
from src.config import HOMEDASH_ELECTRICITY_PRICE
from src.display import format_data_age, format_timestamp
from src.monitoring import HeatPumpMetrics, SystemAlert, build_heat_pump_metrics, build_system_alerts
from src.viessmann_heatpump import feature_values, heat_pump_snapshots_from_inventory
from src.weather import LOCATION_NAME, fetch_forecast, weather_label


def render_monitoring_summary(readings: list[dict[str, object]], database_path: str, timestamps: dict[str, str | None]) -> None:
    heat_pumps = heat_pump_snapshots_from_inventory(get_latest_viessmann_snapshots(database_path))
    metrics: HeatPumpMetrics | None = None
    if heat_pumps:
        metrics = build_heat_pump_metrics(heat_pumps[0], get_viessmann_feature_history(database_path, 24), electricity_price=HOMEDASH_ELECTRICITY_PRICE)
    alerts: list[SystemAlert] = build_system_alerts(readings, timestamps, metrics)
    st.markdown('<div class="level-heading">Systemstatus</div>', unsafe_allow_html=True)
    if not alerts:
        st.success("Keine aktuellen Warnungen. Datenquellen und Heizbetrieb unauffällig.")
    for alert in alerts:
        message = f"**{alert.title}**  \n{alert.detail}"
        if alert.severity == "warning":
            st.warning(message)
        elif alert.severity == "error":
            st.error(message)
        else:
            st.info(message)
    if metrics is None:
        return
    metric_columns = st.columns(4)
    metric_values = (
        ("Energie heute", f"{metrics.produced_energy_today_kwh:.1f} kWh", "erzeugt"),
        ("Stromkosten heute", f"{metrics.daily_energy_cost:.2f} €" if metrics.daily_energy_cost is not None else "n/a", "bei konfiguriertem Strompreis"),
        ("Verdichterstarts", f"{metrics.starts_24h:.0f}" if metrics.starts_24h is not None else "n/a", "letzte 24h"),
        ("Ø Zyklusdauer", f"{metrics.average_cycle_minutes:.1f} min" if metrics.average_cycle_minutes is not None else "n/a", "je Verdichterstart"),
    )
    for column, (label, value, detail) in zip(metric_columns, metric_values):
        with column:
            st.metric(label, value, help=detail)
    below_target = [reading for reading in readings if float(reading["target_temperature"]) - float(reading["current_temperature"]) > 0.5]
    st.caption(
        f"Heizungswirkung: {len(below_target)} Räume liegen mehr als 0,5 °C unter dem Ziel. SPF gesamt: {metrics.spf_total:.1f} · Betriebsmodus: {metrics.operating_mode}."
        if metrics.spf_total is not None
        else f"Heizungswirkung: {len(below_target)} Räume liegen mehr als 0,5 °C unter dem Ziel."
    )


def render_home_dashboard(readings: list[dict[str, object]], database_path: str, provider: str) -> None:
    timestamps = get_latest_data_timestamps(database_path)
    latest_room = f"{format_timestamp(timestamps['homematic'])} ({format_data_age(timestamps['homematic'])})"
    latest_heat_pump = f"{format_timestamp(timestamps['viessmann'])} ({format_data_age(timestamps['viessmann'])})"
    st.markdown(
        f'<section class="home-hero"><div class="home-hero__eyebrow">HomeClimate Dashboard</div><div class="home-hero__title">Dein Zuhause auf einen Blick</div><div class="home-hero__meta">{datetime.now().strftime("%d.%m.%Y")} · Datenprovider {escape(provider)} · Automatische Aktualisierung im festen Raster</div></section>',
        unsafe_allow_html=True,
    )
    render_monitoring_summary(readings, database_path, timestamps)
    room_count = len(readings)
    open_valves = sum(float(reading["valve_position"]) > 0 for reading in readings)
    average_temperature = sum(float(reading["current_temperature"]) for reading in readings) / max(1, room_count)
    st.markdown(
        f'<div class="home-tile-grid"><article class="home-tile"><div class="home-tile__title">Räume</div><div class="home-tile__value">{room_count}</div><div class="home-tile__detail">{open_valves} Ventile geöffnet<br>Ø Raumtemperatur {average_temperature:.1f} °C</div></article><article class="home-tile"><div class="home-tile__title">Datenstatus</div><div class="home-tile__value">Letzte Messwerte</div><div class="home-tile__detail">Homematic {escape(latest_room)}<br>Viessmann {escape(latest_heat_pump)}</div></article></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="level-heading">Wetter & Wärmepumpe</div>', unsafe_allow_html=True)
    overview_columns = st.columns(2)
    with overview_columns[0]:
        try:
            forecast = fetch_forecast().get("daily", {})
            icon, condition = weather_label(int(forecast.get("weather_code", [0])[0]))
            maximum = float(forecast.get("temperature_2m_max", [0])[0])
            minimum = float(forecast.get("temperature_2m_min", [0])[0])
            rain = float(forecast.get("precipitation_sum", [0])[0])
            st.markdown(f'<article class="home-tile"><div class="home-tile__title">Heute in {escape(LOCATION_NAME)}</div><div class="home-tile__value">{icon} {maximum:.0f}° / {minimum:.0f}°C</div><div class="home-tile__detail">{escape(condition)} · Regen {rain:.1f} mm<br>7-Tage-Prognose im Menü Wetter</div></article>', unsafe_allow_html=True)
            if st.button("Wetterbericht öffnen", key="home-weather-detail", width="stretch"):
                st.session_state["pending-navigation"] = "Wetter"
                st.rerun()
        except Exception:
            st.markdown('<article class="home-tile"><div class="home-tile__title">Wetter</div><div class="home-tile__detail">Wetterdaten momentan nicht verfügbar.</div></article>', unsafe_allow_html=True)
    with overview_columns[1]:
        heat_pumps = heat_pump_snapshots_from_inventory(get_latest_viessmann_snapshots(database_path))
        if heat_pumps:
            snapshot = heat_pumps[0]
            feature_rows = {(row["feature"], row["property"]): row["value"] for row in feature_values(snapshot)}
            phase = feature_rows.get(("heating.compressors.0", "phase"), "nicht verfügbar")
            active = str(feature_rows.get(("heating.compressors.0", "active"), "false")).lower() == "true"
            supply = feature_rows.get(("heating.circuits.0.sensors.temperature.supply", "value"), "nicht verfügbar")
            st.markdown(f'<article class="home-tile"><div class="home-tile__title">Wärmepumpe</div><div class="home-tile__value">{"Aktiv" if active else "Bereit"}</div><div class="home-tile__detail">Verdichter: {"aktiv" if active else "bereit"} ({escape(str(phase))})<br>Heizkreis-Vorlauf: {escape(str(supply))} °C</div></article>', unsafe_allow_html=True)
            if st.button("Wärmepumpenbericht öffnen", key="home-heat-pump-detail", width="stretch"):
                st.session_state["pending-navigation"] = "Wärmepumpe"
                st.rerun()
        else:
            st.markdown('<article class="home-tile"><div class="home-tile__title">Wärmepumpe</div><div class="home-tile__detail">Noch keine Viessmann-Daten archiviert.</div></article>', unsafe_allow_html=True)
    st.markdown('<div class="level-heading">Raumstatus</div>', unsafe_allow_html=True)
    room_filter = st.selectbox("Raumfilter", options=("Alle Räume", "Nur geöffnete Ventile"), key="home-room-filter", label_visibility="collapsed")
    filtered_readings = readings if room_filter == "Alle Räume" else [reading for reading in readings if float(reading["valve_position"]) > 0]
    render_overview(filtered_readings, database_path, provider)