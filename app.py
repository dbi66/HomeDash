from datetime import datetime
from html import escape
from urllib.parse import quote

import pandas as pd
import streamlit as st

from src.database import get_latest_data_timestamps, get_latest_readings, get_latest_viessmann_snapshots, get_room_events, get_viessmann_feature_history, get_viessmann_snapshot_history, save_readings, save_viessmann_snapshots
from src.config import DATABASE_PATH, HOMEDASH_ELECTRICITY_PRICE, PROVIDER
from src.dashboard_views import render_compact_chart, render_history, render_overview, render_overview_graphs, render_room_report, render_room_tiles, render_valve_status_table
from src.display import format_data_age, format_timestamp
from src.hmip_provider import HomematicProviderError, load_home, get_room_readings as get_hmip_readings
from src.home_dashboard import render_home_dashboard as render_home_dashboard_page
from src.heat_pump_inventory_view import render_viessmann_inventory
from src.heat_pump_report_view import (
    render_heat_pump_report,
    render_heat_pump_report_page,
)
from src.mock_provider import get_room_readings
from src.monitoring import HeatPumpMetrics, SystemAlert, build_heat_pump_metrics, build_system_alerts
from src.navigation import PAGES, apply_navigation
from src.room_layout import BASE_LEVEL, UNASSIGNED, UPSTAIRS, group_readings_by_level
from src.viessmann_heatpump import feature_values, heat_pump_snapshots_from_inventory, read_heat_pumps, report_sections, system_map
from src.viessmann_provider import ViessmannProviderError, load_client, read_inventory
from src.weather import LOCATION_NAME, fetch_forecast, format_day, weather_label
from src.weather_view import render_weather_report as render_weather_page
from src.settings_view import render_settings_dialog


APP_NAME = "HomeClimate Dashboard"


def render_embedded_html(markup: str, height: int) -> None:
    source = "data:text/html;charset=utf-8," + quote(markup)
    st.iframe(source, width="stretch", height=height)


st.set_page_config(page_title=APP_NAME, page_icon=":house:", layout="wide")

st.markdown(
    """
    <style>
        .stApp {
            background: #f3f7fb;
        }

        [data-testid="stAppViewContainer"] .main .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }

        [data-testid="stVerticalBlock"] {
            gap: 0.1rem;
        }

        [data-testid="stElementContainer"] {
            margin-bottom: 0 !important;
            padding-bottom: 0 !important;
        }

        [data-testid="stHorizontalBlock"] {
            gap: 0.75rem;
        }

        .stApp h3,
        .stApp [data-testid="stMetricLabel"],
        .stApp [data-testid="stMetricValue"],
        .stApp [data-testid="stCaptionContainer"] {
            color: #102a43 !important;
        }

        .stApp [data-testid="stMetricLabel"] {
            font-size: 0.78rem;
            font-weight: 700;
        }

        .stApp [data-testid="stMetricValue"] {
            font-size: 1.35rem;
            font-weight: 800;
        }

        .stApp h3 {
            margin-top: 0.35rem !important;
            margin-bottom: 0.15rem !important;
        }

        .stApp h1,
        .stApp h2 {
            margin-top: 0.35rem !important;
            margin-bottom: 0.15rem !important;
        }

        .weather-grid {
            display: grid;
            gap: 0.7rem;
            grid-template-columns: repeat(7, minmax(120px, 1fr));
            margin: 0.5rem 0 1rem;
            overflow-x: auto;
        }

        .weather-card {
            background: #ffffff;
            border: 1px solid #d9e2ec;
            border-radius: 10px;
            min-width: 120px;
            padding: 0.8rem 0.7rem;
        }

        .weather-card__day { color: #243b53; font-size: 0.85rem; font-weight: 800; }
        .weather-card__icon { color: #1d4ed8 !important; font-size: 2rem; line-height: 1.1; margin: 0.45rem 0; }
        .weather-card__condition { color: #627d98; font-size: 0.78rem; min-height: 2.1rem; }
        .weather-card__temps { color: #102a43; font-size: 1rem; font-weight: 800; margin-top: 0.55rem; }
        .weather-card__meta { color: #627d98; font-size: 0.72rem; line-height: 1.5; margin-top: 0.35rem; }

        .home-hero {
            background: linear-gradient(135deg, #102a43 0%, #243b53 58%, #486581 100%);
            border-radius: 14px;
            color: #ffffff;
            margin: 0.25rem 0 0.75rem;
            padding: 1.15rem 1.25rem;
        }

        .home-hero__eyebrow { color: #bcccdc; font-size: 0.78rem; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
        .home-hero__title { font-size: 1.85rem; font-weight: 800; margin-top: 0.2rem; }
        .home-hero__meta { color: #d9e2ec; font-size: 0.85rem; margin-top: 0.35rem; }
        .home-tile-grid { display: grid; gap: 0.75rem; grid-template-columns: repeat(2, minmax(0, 1fr)); margin: 0.35rem 0 0.8rem; }
        .home-tile { background: #ffffff; border: 1px solid #d9e2ec; border-radius: 10px; min-height: 132px; padding: 0.85rem 1rem; }
        .home-tile__title { color: #102a43; font-size: 1rem; font-weight: 800; }
        .home-tile__subtitle { color: #627d98; font-size: 0.78rem; margin-top: 0.15rem; }
        .home-tile__value { color: #102a43; font-size: 1.55rem; font-weight: 800; margin-top: 0.55rem; }
        .home-tile__detail { color: #486581; font-size: 0.8rem; line-height: 1.55; margin-top: 0.2rem; }

        .home-tile-grid [data-testid="stButton"] button {
            border-color: #9fb3c8;
            color: #102a43;
            font-size: 0.78rem;
            min-height: 34px !important;
            margin-top: 0.35rem;
        }

        @media (max-width: 700px) {
            .home-tile-grid { grid-template-columns: 1fr; }
            .home-hero__title { font-size: 1.45rem; }
        }

        @media (max-width: 800px) {
            .weather-grid { grid-template-columns: repeat(7, minmax(128px, 1fr)); }
        }

        .dashboard-header {
            padding: 0.35rem 0 0.5rem;
        }

        .dashboard-header h1 {
            color: #102a43;
            font-size: 2.1rem;
            letter-spacing: 0;
            margin-bottom: 0.25rem;
        }

        [class*="st-key-refresh-button"] button {
            background: #ffffff;
            border: 1px solid #bcccdc;
            border-radius: 8px;
            color: #102a43;
            min-height: 42px !important;
            padding: 0.45rem 0.8rem !important;
        }

        [class*="st-key-refresh-button"] button p {
            font-size: 0.8rem;
            font-weight: 700;
        }

        .dashboard-header p {
            color: #627d98;
            margin: 0;
        }

        .room-grid {
            display: grid;
            gap: 1rem;
            grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            margin: 1.25rem 0 1.75rem;
        }

        .level-heading {
            color: #102a43;
            font-size: 1.35rem;
            font-weight: 750;
            margin: 0.5rem 0 0.25rem;
        }

        .heat-map-section {
            background: #f7fafc;
            border: 1px solid #d9e2ec;
            border-radius: 8px;
            margin: 0.45rem 0;
            padding: 0.65rem;
        }

        .heat-map-section__title {
            color: #243b53;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            margin-bottom: 0.45rem;
            text-transform: uppercase;
        }

        .heat-pump-schema-wrap {
            background: #f7fafc;
            border: 1px solid #d9e2ec;
            border-radius: 8px;
            overflow-x: auto;
            padding: 0.5rem;
        }

        .heat-pump-schema {
            display: block;
            min-width: 760px;
            width: 100%;
        }

        .schema-pipe {
            fill: none;
            stroke-linecap: round;
            stroke-linejoin: round;
            stroke-width: 8;
        }

        .schema-hot { stroke: #a83b36; }
        .schema-cold { stroke: #385b85; }
        .schema-device, .schema-tank, .schema-dhw { fill: #fff; stroke: #17202a; stroke-width: 2; }
        .schema-tank { fill: #e7edf3; }
        .schema-dhw { fill: #fff7ed; }
        .schema-tank-line { stroke: #9aa5b1; stroke-width: 2; }
        .schema-pump { fill: #fff; stroke: #17202a; stroke-width: 3; }
        .schema-value { fill: #fff; stroke: #7b8794; stroke-width: 1.5; }
        .schema-title, .schema-subtitle, .schema-label, .schema-reading, .schema-state, .schema-sensor, .schema-value-text { font-family: sans-serif; }
        .schema-title { fill: #17202a; font-size: 14px; font-weight: 800; letter-spacing: 1px; }
        .schema-subtitle, .schema-label { fill: #52606d; font-size: 12px; }
        .schema-reading, .schema-value-text { fill: #17202a; font-size: 15px; font-weight: 700; }
        .schema-state { fill: #7b8794; font-size: 12px; }
        .schema-sensor { fill: #17202a; font-size: 17px; font-weight: 800; }

        .heat-map-grid {
            display: grid;
            gap: 0.45rem;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .heat-map-card {
            background: #ffffff;
            border-left: 4px solid #9fb3c8;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(16, 42, 67, 0.06);
            min-height: 76px;
            padding: 0.55rem 0.65rem;
        }

        .heat-map-card.active {
            border-left-color: #2f855a;
        }

        .heat-map-card.sensor {
            border-left-color: #3182ce;
        }

        .heat-map-card__name {
            color: #486581;
            font-size: 0.72rem;
            font-weight: 700;
        }

        .heat-map-card__value {
            color: #102a43;
            font-size: 1rem;
            font-weight: 800;
            margin-top: 0.25rem;
        }

        .heat-map-card__state {
            color: #627d98;
            font-size: 0.68rem;
            margin-top: 0.15rem;
        }

        .room-card {
            border: 1px solid rgba(16, 42, 67, 0.12);
            border-radius: 10px;
            box-shadow: 0 8px 20px rgba(16, 42, 67, 0.08);
            min-height: 154px;
            padding: 0.9rem;
        }

        .room-card__top,
        .room-card__meta,
        .room-card__reading {
            align-items: center;
            display: flex;
            justify-content: space-between;
        }

        .room-card__name {
            color: #102a43;
            font-size: 1.05rem;
            font-weight: 700;
            overflow-wrap: anywhere;
        }

        .room-card__status {
            color: #486581;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .room-card__reading {
            align-items: baseline;
            margin: 1.25rem 0 1rem;
        }

        .room-card__temperature {
            color: #102a43;
            font-size: 2.35rem;
            font-weight: 750;
            line-height: 1;
        }

        .room-card__target {
            color: #486581;
            font-size: 0.85rem;
        }

        .room-card__meta {
            border-top: 1px solid rgba(16, 42, 67, 0.12);
            color: #334e68;
            font-size: 0.84rem;
            padding-top: 0.75rem;
        }

        .room-card__meta strong {
            color: #102a43;
        }

        @media (max-width: 640px) {
            .block-container {
                padding: 1rem 0.75rem 2rem;
            }

            .dashboard-header h1 {
                font-size: 1.6rem;
            }

            .room-grid {
                gap: 0.5rem;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                margin: 0.75rem 0 1.25rem;
            }

            [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
                gap: 0.5rem;
                max-width: calc(100vw - 1.5rem) !important;
                width: calc(100vw - 1.5rem) !important;
            }

            [data-testid="stColumn"] {
                flex: 0 0 calc(50% - 0.25rem);
                min-width: 0;
                width: calc(50% - 0.25rem) !important;
            }

            [data-testid="stHorizontalBlock"]:has(.dashboard-header) {
                flex-wrap: wrap;
            }

            [data-testid="stHorizontalBlock"]:has(.dashboard-header) [data-testid="stColumn"] {
                flex: 0 0 100%;
                width: 100% !important;
            }

            [data-testid="stHorizontalBlock"]:has([data-testid="stVegaLiteChart"]) [data-testid="stColumn"] {
                flex: 0 0 100%;
                width: 100% !important;
            }

            .level-heading {
                font-size: 1.1rem;
                margin-top: 1.2rem;
            }

            .room-card {
                border-radius: 8px;
                min-height: 126px;
                padding: 0.65rem;
            }

            .room-card__name {
                font-size: 0.78rem;
            }

            .room-card__status {
                font-size: 0.55rem;
            }

            .room-card__reading {
                margin: 0.8rem 0 0.65rem;
            }

            .room-card__temperature {
                font-size: 1.35rem;
            }

            .room-card__target {
                font-size: 0.62rem;
            }

            .room-card__meta {
                display: grid;
                font-size: 0.62rem;
                gap: 0.25rem;
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .room-card__meta span {
                white-space: nowrap;
            }

            .stButton button[kind="secondary"] {
                min-height: 96px;
                padding: 0.65rem;
            }

            [class*="st-key-overview-room-"] button p:first-child,
            [class*="st-key-room-tile-"] button p:first-child {
                font-size: 0.72rem;
                overflow-wrap: anywhere;
            }

            [class*="st-key-overview-room-"] button p:nth-child(2),
            [class*="st-key-room-tile-"] button p:nth-child(2) {
                font-size: 0.62rem;
                overflow-wrap: anywhere;
            }

            [class*="st-key-overview-room-"] button > div,
            [class*="st-key-room-tile-"] button > div,
            [class*="st-key-overview-room-"] button p,
            [class*="st-key-room-tile-"] button p {
                min-width: 0;
                white-space: normal;
            }
        }

            .stButton button[kind="secondary"] {
                background: #dbeafe;
                border: 1px solid rgba(16, 42, 67, 0.12);
                border-radius: 10px;
                color: #102a43;
                min-height: 96px;
                text-align: left;
                white-space: pre-wrap;
            }

            .stButton button[kind="secondary"] p {
                font-size: 0.78rem;
                line-height: 1.35;
            }

                .device-tree {
                    background: #eef5fb;
                    border: 1px solid #c9d8e6;
                    border-radius: 10px;
                    margin-top: 0.75rem;
                    padding: 1rem;
                }

                .device-tree__root {
                    align-items: center;
                    background: #102a43;
                    border-radius: 8px;
                    color: #ffffff;
                    display: flex;
                    font-weight: 700;
                    gap: 0.6rem;
                    padding: 0.7rem 0.85rem;
                }

                .device-tree__branch {
                    border-left: 2px solid #9fb3c8;
                    margin: 0.5rem 0 0 0.9rem;
                    padding-left: 1rem;
                }

                .device-node {
                    background: #ffffff;
                    border: 1px solid #d9e2ec;
                    border-radius: 8px;
                    margin: 0.55rem 0;
                    padding: 0.7rem;
                }

                .device-node__title {
                    color: #102a43;
                    font-size: 0.9rem;
                    font-weight: 700;
                }

                .device-node__model {
                    color: #627d98;
                    font-size: 0.75rem;
                    margin-left: 0.35rem;
                }

                .channel-chip {
                    background: #dbeafe;
                    border-radius: 999px;
                    color: #243b53;
                    display: inline-block;
                    font-size: 0.7rem;
                    margin: 0.45rem 0.35rem 0 0;
                    padding: 0.25rem 0.5rem;
                }

                [class*="st-key-settings-button"] button p {
                    font-size: 1.45rem;
                    line-height: 1;
                }

                [class*="st-key-overview-room-"] button p:first-child,
                [class*="st-key-room-tile-"] button p:first-child {
                    color: #102a43;
                    font-size: 0.95rem;
                    font-weight: 800;
                    line-height: 1.2;
                }

                [class*="st-key-overview-room-"] button p:nth-child(2),
                [class*="st-key-room-tile-"] button p:nth-child(2) {
                    color: #486581;
                    font-size: 0.72rem;
                    font-weight: 500;
                    line-height: 1.25;
                }

                [class*="st-key-overview-room-"] button > div,
                [class*="st-key-room-tile-"] button > div {
                    display: block !important;
                    width: 100%;
                }

                [class*="st-key-overview-room-"] button p,
                [class*="st-key-room-tile-"] button p {
                    display: block !important;
                    margin: 0;
                    width: 100%;
                }

                [class*="st-key-function-navigation"] {
                    min-width: 190px;
                }

                [data-testid="stCheckbox"] label p {
                    color: #334e68 !important;
                    font-size: 0.78rem;
                    font-weight: 700;
                }
    </style>
    """,
    unsafe_allow_html=True,
)


def collect_readings():
    if PROVIDER == "homematic":
        return get_hmip_readings()
    return get_room_readings()


def load_readings() -> list[dict[str, object]]:
    readings = get_latest_readings(DATABASE_PATH)
    if not readings:
        save_readings(DATABASE_PATH, collect_readings())
        readings = get_latest_readings(DATABASE_PATH)
    return readings


def render_device_hierarchy(home: object) -> None:
    devices = sorted(
        getattr(home, "devices", []),
        key=lambda device: str(getattr(device, "label", "")).lower(),
    )
    nodes = []
    for device in devices:
        label = str(getattr(device, "label", "Unnamed device"))
        model = str(getattr(device, "modelType", "Unknown model"))
        channels = sorted(
            getattr(device, "functionalChannels", []),
            key=lambda item: int(getattr(item, "index", 0)),
        )
        chips = []
        for channel in channels:
            channel_type = escape(str(getattr(channel, "functionalChannelType", "Unknown channel")))
            channel_label = escape(str(getattr(channel, "label", "")))
            channel_index = escape(str(getattr(channel, "index", "?")))
            title = f"{channel_index}: {channel_type}"
            if channel_label:
                title = f"{title} | {channel_label}"
            chips.append(f'<span class="channel-chip">{title}</span>')
        channel_html = "".join(chips) or '<span class="channel-chip">No channels</span>'
        nodes.append(
            f'<div class="device-node"><div class="device-node__title">{escape(label)}'
            f'<span class="device-node__model">{escape(model)}</span></div>{channel_html}</div>'
        )
    tree = (
        f'<div class="device-tree"><div class="device-tree__root">HomeClimate'
        f'<span class="device-tree__model">{len(devices)} devices</span></div>'
        f'<div class="device-tree__branch">{"".join(nodes)}</div></div>'
    )
    st.markdown(tree, unsafe_allow_html=True)


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


def render_monitoring_summary(
    readings: list[dict[str, object]],
    database_path: str,
    timestamps: dict[str, str | None],
) -> None:
    heat_pumps = heat_pump_snapshots_from_inventory(get_latest_viessmann_snapshots(database_path))
    metrics: HeatPumpMetrics | None = None
    if heat_pumps:
        metrics = build_heat_pump_metrics(
            heat_pumps[0],
            get_viessmann_feature_history(database_path, 24),
            electricity_price=HOMEDASH_ELECTRICITY_PRICE,
        )
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
        ("Stromkosten heute", f"{metrics.daily_energy_cost:.2f} €" if metrics.daily_energy_cost is not None else "n/a", "bei 0,30 €/kWh"),
        ("Verdichterstarts", f"{metrics.starts_24h:.0f}" if metrics.starts_24h is not None else "n/a", "letzte 24h"),
        ("Ø Zyklusdauer", f"{metrics.average_cycle_minutes:.1f} min" if metrics.average_cycle_minutes is not None else "n/a", "je Verdichterstart"),
    )
    for column, (label, value, detail) in zip(metric_columns, metric_values):
        with column:
            st.metric(label, value, help=detail)

    below_target = [
        reading for reading in readings
        if float(reading["target_temperature"]) - float(reading["current_temperature"]) > 0.5
    ]
    st.caption(
        f"Heizungswirkung: {len(below_target)} Räume liegen mehr als 0,5 °C unter dem Ziel. "
        f"SPF gesamt: {metrics.spf_total:.1f} · Betriebsmodus: {metrics.operating_mode}."
        if metrics.spf_total is not None
        else f"Heizungswirkung: {len(below_target)} Räume liegen mehr als 0,5 °C unter dem Ziel."
    )


def render_home_dashboard(readings: list[dict[str, object]], database_path: str, provider: str) -> None:
    timestamps = get_latest_data_timestamps(database_path)
    latest_room = f"{format_timestamp(timestamps['homematic'])} ({format_data_age(timestamps['homematic'])})"
    latest_heat_pump = f"{format_timestamp(timestamps['viessmann'])} ({format_data_age(timestamps['viessmann'])})"
    now = datetime.now().strftime("%d.%m.%Y")
    st.markdown(
        f'<section class="home-hero"><div class="home-hero__eyebrow">HomeClimate Dashboard</div>'
        f'<div class="home-hero__title">Dein Zuhause auf einen Blick</div>'
        f'<div class="home-hero__meta">{escape(now)} · Datenprovider {escape(provider)} · Automatische Aktualisierung im festen Raster</div></section>',
        unsafe_allow_html=True,
    )
    render_monitoring_summary(readings, database_path, timestamps)

    room_count = len(readings)
    open_valves = sum(float(reading["valve_position"]) > 0 for reading in readings)
    average_temperature = sum(float(reading["current_temperature"]) for reading in readings) / max(1, room_count)
    st.markdown(
        f'<div class="home-tile-grid">'
        f'<article class="home-tile"><div class="home-tile__title">Räume</div><div class="home-tile__value">{room_count}</div><div class="home-tile__detail">{open_valves} Ventile geöffnet<br>Ø Raumtemperatur {average_temperature:.1f} °C</div></article>'
        f'<article class="home-tile"><div class="home-tile__title">Datenstatus</div><div class="home-tile__value">Letzte Messwerte</div><div class="home-tile__detail">Homematic {escape(latest_room)}<br>Viessmann {escape(latest_heat_pump)}</div></article>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="level-heading">Wetter & Wärmepumpe</div>', unsafe_allow_html=True)
    overview_columns = st.columns(2)
    with overview_columns[0]:
        try:
            forecast = fetch_forecast().get("daily", {})
            code = int(forecast.get("weather_code", [0])[0])
            icon, condition = weather_label(code)
            maximum = float(forecast.get("temperature_2m_max", [0])[0])
            minimum = float(forecast.get("temperature_2m_min", [0])[0])
            rain = float(forecast.get("precipitation_sum", [0])[0])
            st.markdown(
                f'<article class="home-tile"><div class="home-tile__title">Heute in {escape(LOCATION_NAME)}</div>'
                f'<div class="home-tile__value">{icon} {maximum:.0f}° / {minimum:.0f}°C</div>'
                f'<div class="home-tile__detail">{escape(condition)} · Regen {rain:.1f} mm<br>7-Tage-Prognose im Menü Wetter</div></article>',
                unsafe_allow_html=True,
            )
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
            st.markdown(
                f'<article class="home-tile"><div class="home-tile__title">Wärmepumpe</div>'
                f'<div class="home-tile__value">{"Aktiv" if active else "Bereit"}</div>'
                f'<div class="home-tile__detail">Verdichter: {"aktiv" if active else "bereit"} ({escape(str(phase))})<br>Heizkreis-Vorlauf: {escape(str(supply))} °C</div></article>',
                unsafe_allow_html=True,
            )
            if st.button("Wärmepumpenbericht öffnen", key="home-heat-pump-detail", width="stretch"):
                st.session_state["pending-navigation"] = "Wärmepumpe"
                st.rerun()
        else:
            st.markdown('<article class="home-tile"><div class="home-tile__title">Wärmepumpe</div><div class="home-tile__detail">Noch keine Viessmann-Daten archiviert.</div></article>', unsafe_allow_html=True)

    st.markdown('<div class="level-heading">Raumstatus</div>', unsafe_allow_html=True)
    room_filter = st.selectbox(
        "Raumfilter",
        options=("Alle Räume", "Nur geöffnete Ventile"),
        key="home-room-filter",
        label_visibility="collapsed",
    )
    filtered_readings = readings if room_filter == "Alle Räume" else [
        reading for reading in readings if float(reading["valve_position"]) > 0
    ]
    render_overview(filtered_readings, database_path, provider)


header_actions = st.columns([6, 2, 3])
with header_actions[0]:
    st.markdown(
        f'<div class="dashboard-header"><h1>{escape(APP_NAME)}</h1></div>',
        unsafe_allow_html=True,
    )
    timestamps = get_latest_data_timestamps(DATABASE_PATH)
    st.caption(
        "Letzte Daten: "
        f"Homematic {format_timestamp(timestamps['homematic'])} ({format_data_age(timestamps['homematic'])}) | "
        f"Viessmann {format_timestamp(timestamps['viessmann'])} ({format_data_age(timestamps['viessmann'])})"
    )
with header_actions[1]:
    if st.button("Neu laden", key="refresh-button", help="Seite neu darstellen; Datenabfragen laufen automatisch im festen Raster.", width="stretch"):
        st.rerun()
with header_actions[2]:
    route_hint = {
        "detail": "Raumdetail",
        "report": "Raumbericht",
    }.get(st.query_params.get("view"), "Home")
    if route_hint == "Raumdetail" and "function-navigation" not in st.session_state:
        st.session_state["function-navigation"] = "Raumdetail"
    if "navigation-last" not in st.session_state:
        st.session_state["navigation-last"] = route_hint
    elif route_hint == "Raumdetail" and st.session_state["navigation-last"] == "Home":
        st.session_state["navigation-last"] = "Raumdetail"

    pending_navigation = st.session_state.pop("pending-navigation", None)
    pending_room = st.session_state.pop("pending-room", None)
    pending_view = st.session_state.pop("pending-view", None)
    if pending_navigation:
        st.session_state["function-navigation"] = pending_navigation
    if pending_room:
        st.session_state["selected_room"] = pending_room
    if pending_view:
        st.session_state["view"] = pending_view

    function_choice = st.selectbox(
        "Navigation",
        options=PAGES,
        key="function-navigation",
        label_visibility="collapsed",
    )

help_text = {
    "Home": "Zeigt Raumkacheln nach Etage. Temperatur, Luftfeuchte, Zieltemperatur und Ventilstellung stammen aus dem letzten Homematic-Snapshot.",
    "Raumdetail": "Zeigt den gewählten Raum mit Historie, Verläufen und Ereignissen. Die Ansicht verändert keine Heizungswerte.",
    "Raumbericht": "Vergleicht alle Räume über Temperatur- und Feuchtigkeitsdiagramme und zeigt den Ventilstatus als Tabelle.",
    "Alle Diagramme": "Zeigt die Raumverläufe kompakt für 24 Stunden, 7 Tage oder 30 Tage.",
    "Wärmepumpe": "Zeigt Viessmann-Schemata, KPIs, Heizkurve, Betriebszustände, Temperaturen, Energie- und Snapshot-Historie.",
    "Wetter": "Zeigt die 7-Tage-Vorhersage für Aystetten (86482) mit Wetterlage, Temperatur, Niederschlag und Wind.",
    "Einstellungen": "Erlaubt das read-only Einlesen von Homematic- und Viessmann-Daten. Heizungsparameter werden nicht geschrieben.",
}.get(function_choice, "Diese Seite zeigt gespeicherte Monitoringdaten.")
with st.popover("Hilfe"):
    st.markdown("### Diese Seite")
    st.write(help_text)
    st.markdown("### Datenaktualisierung")
    st.write("**Neu laden** rendert nur die Seite neu. Homematic wird automatisch alle 15 Minuten, Viessmann alle 30 Minuten gelesen. Der Zeitstempel im Kopf zeigt den letzten gespeicherten Messwert.")

st.markdown(
    "<div style=\"background:#ffffff;border:1px solid #d9e2ec;border-radius:8px;"
    "color:#486581;font-size:0.85rem;margin:0.25rem 0 1rem;padding:0.5rem 0.75rem;\">"
    "Letzte Daten: "
    f"Homematic {escape(format_timestamp(timestamps['homematic']))} | "
    f"Viessmann {escape(format_timestamp(timestamps['viessmann']))}"
    "</div>",
    unsafe_allow_html=True,
)
previous_choice = st.session_state.get("navigation-last")
st.session_state["navigation-last"] = function_choice

apply_navigation(function_choice, st.session_state, st.query_params)

if st.session_state.get("show_settings", False):
    render_settings_dialog(
        database_path=DATABASE_PATH,
        load_home=load_home,
        load_client=load_client,
        read_inventory=read_inventory,
        read_heat_pumps=read_heat_pumps,
        save_viessmann_snapshots=save_viessmann_snapshots,
        latest_viessmann_snapshots=get_latest_viessmann_snapshots,
        heat_pumps_from_inventory=heat_pump_snapshots_from_inventory,
        render_device_hierarchy=render_device_hierarchy,
        render_viessmann_inventory=render_viessmann_inventory,
        homematic_error=HomematicProviderError,
        viessmann_error=ViessmannProviderError,
    )

if function_choice == "Wetter":
    render_weather_page()
    st.stop()

if function_choice == "Wärmepumpe":
    snapshot_history = get_viessmann_snapshot_history(DATABASE_PATH)
    archived_heat_pumps = heat_pump_snapshots_from_inventory(
        get_latest_viessmann_snapshots(DATABASE_PATH)
    )
    if archived_heat_pumps:
        render_heat_pump_report_page(archived_heat_pumps[0], snapshot_history, render_heat_pump_report)
    else:
        st.info("Noch keine Wärmepumpen-Daten vorhanden. Bitte zuerst in Einstellungen einlesen.")
    st.stop()

try:
    readings = load_readings()
except HomematicProviderError as error:
    st.error(str(error))
    st.info("Set HOMEDASH_PROVIDER=mock to run without Homematic IP hardware.")
    readings = get_latest_readings(DATABASE_PATH)

if not readings:
    st.warning("No room readings are available yet.")
    st.stop()

room_names = sorted({str(reading["room_name"]) for reading in readings})
query_room = st.query_params.get("room")
page = pending_view or st.session_state.get("view", st.query_params.get("view", "detail" if query_room else "overview"))
selected_room = pending_room or query_room or st.session_state.get("selected_room", room_names[0])
if selected_room not in room_names:
    selected_room = room_names[0]
st.session_state["selected_room"] = selected_room


if page == "report":
    render_room_report(readings)
    st.stop()

if page == "overview":
    if st.session_state.get("show_all_graphs", False):
        render_overview_graphs(room_names, DATABASE_PATH)
    else:
        render_home_dashboard_page(readings, str(DATABASE_PATH), PROVIDER)
    st.stop()


with st.container(border=True):
    history_room = st.selectbox("Selected room", room_names, index=room_names.index(selected_room))
    if history_room != selected_room:
        selected_room = history_room
        st.session_state["selected_room"] = selected_room
        st.query_params["room"] = selected_room
        st.rerun()
    else:
        st.query_params["room"] = selected_room
    render_history(selected_room, DATABASE_PATH)
    selected_reading = next(
        reading for reading in readings if str(reading["room_name"]) == selected_room
    )
    st.markdown("### Ventilstatus")
    render_valve_status_table([selected_reading])
    if st.button("Event log", key="event-log-button", width="stretch"):
        st.session_state["show_event_log"] = not st.session_state.get("show_event_log", False)
        st.rerun()
    if st.session_state.get("show_event_log", False):
        events = get_room_events(DATABASE_PATH, selected_room)
        if not events:
            st.caption("No valve or target-temperature events recorded yet.")
        else:
            for event in events:
                st.write(f"{event['recorded_at']}  |  {event['message']}")

if st.session_state.get("show_all_graphs", False):
    with st.container(border=True):
        st.markdown("### Alle Diagramme")
        all_graph_hours = st.selectbox(
            "History range for all rooms",
            options=(24, 168, 720),
            format_func=lambda hours: {24: "Last 24 hours", 168: "Last 7 days", 720: "Last 30 days"}[hours],
            key="all-graphs-window",
        )
        graph_columns = st.columns(2)
        for index, room_name in enumerate(room_names):
            with graph_columns[index % 2]:
                render_compact_chart(room_name, DATABASE_PATH, all_graph_hours)


grouped_readings = group_readings_by_level(readings)
for level in (UPSTAIRS, BASE_LEVEL, UNASSIGNED):
    level_readings = grouped_readings.get(level, [])
    if level_readings:
        st.markdown(
            f'<div style="color:#102a43;font-size:1.35rem;font-weight:750;margin:1.75rem 0 0.25rem;">{escape(level)}</div>',
            unsafe_allow_html=True,
        )
        render_room_tiles(level_readings)

with st.expander("Letzte Messwerte"):
    st.dataframe(
        pd.DataFrame(readings),
        hide_index=True,
        width="stretch",
        column_config={
            "room_name": "Raum",
            "current_temperature": st.column_config.NumberColumn("Ist (°C)", format="%.1f"),
            "target_temperature": st.column_config.NumberColumn("Ziel (°C)", format="%.1f"),
            "humidity": st.column_config.NumberColumn("Feuchte (%)", format="%.0f"),
            "valve_position": st.column_config.NumberColumn("Ventil (%)", format="%.0f"),
            "recorded_at": "Gemessen am",
        },
    )

st.caption(f"Data provider: {PROVIDER}")
