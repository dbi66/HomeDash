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
from src.heat_pump_page import render_heat_pump_page
from src.mock_provider import get_room_readings
from src.monitoring import HeatPumpMetrics, SystemAlert, build_heat_pump_metrics, build_system_alerts
from src.room_layout import BASE_LEVEL, UNASSIGNED, UPSTAIRS, group_readings_by_level
from src.viessmann_heatpump import feature_values, heat_pump_snapshots_from_inventory, read_heat_pumps, report_sections, system_map
from src.viessmann_provider import ViessmannProviderError, load_client, read_inventory
from src.weather import LOCATION_NAME, fetch_forecast, format_day, weather_label
from src.weather_view import render_weather_report as render_weather_page


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


def render_viessmann_inventory(inventory: list[dict[str, object]]) -> None:
    st.caption(f"{len(inventory)} Viessmann device(s)")
    for device in inventory:
        features = device.get("features", {})
        feature_rows = features.get("data", []) if isinstance(features, dict) else []
        with st.expander(f"{device['model']} | {device['id']} | {'online' if device['online'] else 'offline'}"):
            if not feature_rows:
                st.json(features)
                continue
            rows = []
            for feature in feature_rows:
                if isinstance(feature, dict):
                    rows.append(
                        {
                            "feature": feature.get("feature", ""),
                            "properties": ", ".join(sorted(feature.get("properties", {}).keys())),
                        }
                    )
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            else:
                st.json(features)


def render_viessmann_heat_pumps(heat_pumps: list[object]) -> None:
    st.caption(f"{len(heat_pumps)} Viessmann heat pump(s), read-only")
    selected_index = st.selectbox(
        "Wärmepumpe auswählen",
        options=range(len(heat_pumps)),
        format_func=lambda index: (
            f"{heat_pumps[index].model} | {heat_pumps[index].device_id} | "
            f"{'online' if heat_pumps[index].online else 'offline'}"
        ),
        key="viessmann-heat-pump-report-selection",
        )
    snapshot = heat_pumps[selected_index]
    rows = feature_values(snapshot)
    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            width="stretch",
            column_config={
                "feature": "Feature",
                "property": "Property",
                "value": "Value",
                "unit": "Unit",
            },
        )
    else:
        st.info("No flattened feature values were returned for this heat pump.")
    with st.expander("Complete raw Viessmann data"):
        st.json(snapshot.features)


def render_heat_pump_schema(snapshot: object) -> None:
    items = {
        item["name"]: item
        for group in system_map(snapshot).values()
        for item in group
    }

    def value(name: str) -> str:
        raw_value = str(items.get(name, {}).get("value") or "nicht verfügbar")
        readable_value = raw_value.replace(" celsius", " °C").replace(" percent", " %")
        return {
            "heating": "Heizen",
            "standby": "Bereitschaft",
            "efficientwithmincomfort": "Komfortbetrieb",
            "true": "Ja",
            "false": "Nein",
        }.get(readable_value.lower(), readable_value)

    def state(name: str) -> str:
        return str(items.get(name, {}).get("state") or "")

    def text(value_text: str, x: int, y: int, width: int = 150) -> str:
        return (
            f'<rect x="{x}" y="{y}" width="{width}" height="34" class="schema-value"/>'
            f'<text x="{x + width / 2}" y="{y + 23}" text-anchor="middle" class="schema-value-text">'
            f'{escape(value_text)}</text>'
        )

    def sensor(x: int, y: int, label: str, reading: str, color: str = "#17202a") -> str:
        return (
            f'<circle cx="{x}" cy="{y}" r="16" fill="#fff" stroke="{color}" stroke-width="3"/>'
            f'<text x="{x}" y="{y + 6}" text-anchor="middle" class="schema-sensor">i</text>'
            f'<text x="{x}" y="{y + 38}" text-anchor="middle" class="schema-label">{escape(label)}</text>'
            f'<text x="{x}" y="{y + 57}" text-anchor="middle" class="schema-reading">{escape(reading)}</text>'
        )

    active_color = "#b43a32" if state("Verdichter").lower() in {"true", "on", "active", "heating"} else "#b9c2cc"
    compressor_state = "aktiv" if active_color == "#b43a32" else "aus / bereit"
    heating_rod_ready = state("Inneneinheit Heizstab").lower() in {"true", "on", "active", "heating"}
    heating_rod_color = "#c98b4a" if heating_rod_ready else "#b9c2cc"
    heating_rod_state = "bereit / heizt nicht" if heating_rod_ready else "gesperrt"
    schema = f'''
        <style>
            html, body {{ margin: 0; background: #f7fafc; }}
            .heat-pump-schema-wrap {{ background: #f7fafc; padding: 8px; overflow-x: auto; }}
            .heat-pump-schema {{ display: block; min-width: 0; max-width: 100%; width: 100%; }}
            .schema-pipe {{ fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 8; }}
            .schema-hot {{ stroke: #a83b36; }} .schema-cold {{ stroke: #385b85; }}
            .schema-dhw-pipe {{ fill: none; stroke: #c98b4a; stroke-linecap: round; stroke-linejoin: round; stroke-width: 5; }}
            .schema-device, .schema-tank, .schema-dhw {{ fill: #fff; stroke: #17202a; stroke-width: 2; }}
            .schema-buffer {{ fill: url(#schema-buffer-gradient); stroke: #17202a; stroke-width: 2; }}
            .schema-dhw {{ fill: #fff7ed; stroke: #17202a; stroke-width: 2; }}
            .schema-tank-line {{ stroke: #9aa5b1; stroke-width: 2; }}
            .schema-buffer-coil {{ fill: none; stroke: #f7fafc; stroke-width: 5; stroke-linecap: round; }}
            .schema-pump {{ fill: #fff; stroke: #17202a; stroke-width: 3; }}
            .schema-title, .schema-subtitle, .schema-label, .schema-reading, .schema-state, .schema-sensor {{ font-family: sans-serif; }}
            .schema-title, .schema-subtitle, .schema-label, .schema-reading, .schema-state {{ paint-order: stroke fill; stroke: #f7fafc; stroke-width: 5px; stroke-linejoin: round; }}
            .schema-title {{ fill: #17202a; font-size: 14px; font-weight: 800; letter-spacing: 1px; }}
            .schema-subtitle, .schema-label {{ fill: #52606d; font-size: 12px; }}
            .schema-reading {{ fill: #17202a; font-size: 15px; font-weight: 700; }}
            .schema-state {{ fill: #7b8794; font-size: 12px; }} .schema-sensor {{ fill: #17202a; font-size: 17px; font-weight: 800; }}
        </style>
        <div class="heat-pump-schema-wrap">
    <svg class="heat-pump-schema" viewBox="0 0 1200 500" role="img" aria-label="Hydraulisches Schema der Wärmepumpe">
        <defs>
          <marker id="schema-arrow-red" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#a83b36"/></marker>
          <marker id="schema-arrow-blue" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#385b85"/></marker>
                    <linearGradient id="schema-buffer-gradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#c51f1f"/>
                        <stop offset="0.48" stop-color="#5b3d75"/>
                        <stop offset="1" stop-color="#1976d2"/>
                    </linearGradient>
        </defs>
        <path d="M420 180 V125 H400 V170 H920" class="schema-pipe schema-hot" marker-end="url(#schema-arrow-red)"/>
        <path d="M920 80 V385 H720 V430 H420 V300" class="schema-pipe schema-cold" marker-end="url(#schema-arrow-blue)"/>
        <path d="M400 80 V230 H510 V385" class="schema-pipe schema-hot"/>
        <path d="M510 385 V230 H400" class="schema-pipe schema-cold"/>
        <path d="M720 430 V310 H610 V230" class="schema-pipe schema-cold"/>
        <path d="M610 230 H720 V125" class="schema-pipe schema-hot"/>
        <path d="M720 170 V125" class="schema-pipe schema-hot"/>
        <path d="M720 125 V260 H820" class="schema-pipe schema-hot"/>
        <path d="M820 380 H720 V430" class="schema-pipe schema-cold"/>

        <rect x="72" y="145" width="190" height="225" rx="8" class="schema-device"/>
        <text x="167" y="182" text-anchor="middle" class="schema-title">AUSSENEINHEIT</text>
        <text x="167" y="207" text-anchor="middle" class="schema-subtitle">{escape(snapshot.model)}</text>
        <circle cx="167" cy="256" r="31" fill="none" stroke="{active_color}" stroke-width="8"/>
        <path d="M167 225 L177 256 L167 287 L157 256 Z" fill="{active_color}"/>
        <text x="167" y="312" text-anchor="middle" class="schema-state">Verdichter {compressor_state}</text>
        <text x="112" y="340" text-anchor="middle" class="schema-label" style="font-size:10px">LÜFTER 1</text>
        <text x="112" y="356" text-anchor="middle" class="schema-reading" style="font-size:13px">{escape(value("Außenlüfter 1"))}</text>
        <text x="185" y="340" text-anchor="middle" class="schema-label" style="font-size:10px">LÜFTER 2</text>
        <text x="185" y="356" text-anchor="middle" class="schema-reading" style="font-size:13px">{escape(value("Außenlüfter 2"))}</text>

        <path d="M262 225 H280" class="schema-pipe schema-hot"/>
        <path d="M262 300 H280" class="schema-pipe schema-cold"/>
        <rect x="280" y="210" width="140" height="120" rx="8" class="schema-device"/>
        <text x="350" y="238" text-anchor="middle" class="schema-title" style="font-size:11px">INNENEINHEIT</text>
        <circle cx="320" cy="270" r="20" class="schema-pump"/>
        <path d="M309 270 Q320 254 331 270 Q320 286 309 270" fill="none" stroke="#17202a" stroke-width="2"/>
        <text x="320" y="306" text-anchor="middle" class="schema-state">Pumpe {escape(value("Inneneinheit Pumpe"))}</text>
        <path d="M390 250 L380 270 H389 L384 290 L402 265 H393 Z" fill="{heating_rod_color}"/>
        <text x="390" y="306" text-anchor="middle" class="schema-label" style="font-size:9px">HEIZSTAB</text>
        <text x="390" y="320" text-anchor="middle" class="schema-state" style="font-size:9px">{heating_rod_state}</text>

        <rect x="440" y="155" width="140" height="230" rx="8" class="schema-buffer"/>
        <text x="510" y="185" text-anchor="middle" class="schema-title">PUFFER</text>
        <path d="M460 220 H560 M460 270 H560 M460 320 H560" class="schema-tank-line"/>
        <path d="M468 250 C550 225 550 285 468 270 C550 250 550 310 468 295" class="schema-buffer-coil"/>
        <text x="510" y="365" text-anchor="middle" class="schema-reading">{escape(value("Pufferspeicher"))}</text>

        <circle cx="720" cy="125" r="28" class="schema-pump"/>
        <path d="M705 125 Q720 104 735 125 Q720 146 705 125" fill="none" stroke="#17202a" stroke-width="3"/>
        <text x="720" y="170" text-anchor="middle" class="schema-label">Heizkreispumpe</text>
        <text x="720" y="190" text-anchor="middle" class="schema-reading">{escape(value("Heizkreis 1 Pumpe"))}</text>

        <circle cx="610" cy="230" r="28" class="schema-pump"/>
        <path d="M595 230 Q610 209 625 230 Q610 251 595 230" fill="none" stroke="#17202a" stroke-width="3"/>
        <text x="610" y="263" text-anchor="middle" class="schema-label">Interne Pumpe</text>
        <text x="610" y="283" text-anchor="middle" class="schema-reading">{escape(value("Interne Pumpe"))}</text>

        <path d="M820 260 H980 V280 H820 V300 H980 V320 H820" class="schema-pipe schema-hot"/>
        <path d="M820 320 H980 V340 H820 V360 H980 V380 H820" class="schema-pipe schema-cold"/>
        <text x="900" y="410" text-anchor="middle" class="schema-title" style="font-size:11px">FUSSBODENHEIZUNG</text>
        <text x="900" y="430" text-anchor="middle" class="schema-reading">Vorlauf {escape(value("Heizkreis 1 Vorlauf"))}</text>

        <path d="M580 58 Q640 35 700 58 V130 Q640 153 580 130 Z" class="schema-dhw"/>
        <ellipse cx="640" cy="58" rx="60" ry="23" class="schema-dhw"/>
        <path d="M580 130 Q640 107 700 130" fill="none" stroke="#c98b4a" stroke-width="2"/>
        <text x="640" y="78" text-anchor="middle" class="schema-title" style="font-size:11px">WARMWASSER</text>
        <text x="640" y="94" text-anchor="middle" class="schema-title" style="font-size:11px">SPEICHER</text>
        <text x="640" y="119" text-anchor="middle" class="schema-reading">{escape(value("Warmwasser"))}</text>
        <path d="M640 153 V190 H820 V215 H640 V153" class="schema-dhw-pipe"/>
        <circle cx="820" cy="202" r="16" fill="#fff7ed" stroke="#c98b4a" stroke-width="3"/>
        <path d="M812 202 Q820 192 828 202 Q820 212 812 202" fill="none" stroke="#c98b4a" stroke-width="2"/>
        <text x="980" y="215" text-anchor="middle" class="schema-label" style="font-size:10px">HAUSINTERNE ZIRKULATION</text>
        <text x="980" y="230" text-anchor="middle" class="schema-state">{escape(value("Warmwasser-Zirkulation"))}</text>

        {sensor(320, 125, "Gemeinsamer Vorlauf", value("Gemeinsamer Vorlauf"), "#a83b36")}
        {sensor(400, 80, "Außentemperatur", value("Außentemperatur"), "#385b85")}
        {sensor(510, 430, "Pufferspeicher", value("Pufferspeicher"), "#385b85")}
        {sensor(1010, 260, "Heizkreis Vorlauf", value("Heizkreis 1 Vorlauf"), "#a83b36")}
        {sensor(1040, 385, "Anlagenrücklauf", value("Gemeinsamer Vorlauf"), "#385b85")}
      </svg>
    </div>
    '''
    render_embedded_html(schema, 520)


def render_clear_heat_pump_schema(snapshot: object) -> None:
        items = {
                item["name"]: item
                for group in system_map(snapshot).values()
                for item in group
        }

        def value(name: str) -> str:
                raw_value = str(items.get(name, {}).get("value") or "nicht verfügbar")
                readable_value = raw_value.replace(" celsius", " °C").replace(" percent", " %")
                return {
                        "heating": "Heizen",
                        "standby": "Bereitschaft",
                        "efficientwithmincomfort": "Komfortbetrieb",
                        "true": "Ja",
                        "false": "Nein",
                }.get(readable_value.lower(), readable_value)

        def state(name: str) -> str:
                return str(items.get(name, {}).get("state") or "")

        def status(name: str) -> str:
                return "aktiv" if state(name).lower() in {"true", "on", "active", "heating"} else "bereit / aus"

        compressor_active = state("Verdichter").lower() in {"true", "on", "active", "heating"}
        rod_ready = state("Inneneinheit Heizstab").lower() in {"true", "on", "active", "heating"}
        schema = f'''
        <style>
            html, body {{ margin: 0; background: #f7fafc; }}
            .clear-schema-wrap {{ background: #f7fafc; padding: 12px; overflow-x: auto; }}
            .clear-schema {{ display: block; width: 100%; max-width: 100%; }}
            .clear-pipe {{ fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 7; }}
            .clear-hot {{ stroke: #a83b36; }} .clear-cold {{ stroke: #385b85; }} .clear-dhw {{ stroke: #c98b4a; }}
            .clear-box {{ fill: #fff; stroke: #17202a; stroke-width: 2; }}
            .clear-buffer {{ fill: url(#clear-buffer-gradient); stroke: #17202a; stroke-width: 2; }}
            .clear-floor {{ fill: none; stroke-linecap: round; stroke-width: 6; }}
            .clear-floor-hot {{ stroke: #a83b36; }} .clear-floor-cold {{ stroke: #385b85; }}
            .clear-title, .clear-label, .clear-value, .clear-state {{ font-family: sans-serif; paint-order: stroke fill; stroke: #f7fafc; stroke-width: 5px; stroke-linejoin: round; }}
            .clear-title {{ fill: #17202a; font-size: 15px; font-weight: 800; letter-spacing: .8px; }}
            .clear-label {{ fill: #52606d; font-size: 12px; }}
            .clear-value {{ fill: #17202a; font-size: 15px; font-weight: 700; }}
            .clear-state {{ fill: #52606d; font-size: 11px; }}
            .clear-sensor {{ fill: #fff; stroke: #17202a; stroke-width: 2; }}
        </style>
        <div class="clear-schema-wrap">
            <svg class="clear-schema" viewBox="0 0 1200 600" role="img" aria-label="Klar strukturiertes Viessmann Heizungs- und Warmwasserschema">
                <defs>
                    <linearGradient id="clear-buffer-gradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#c51f1f"/><stop offset="0.5" stop-color="#5b3d75"/><stop offset="1" stop-color="#1976d2"/>
                    </linearGradient>
                      <marker id="clear-arrow-hot" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto"><path d="M0,0 L4.5,2.5 L0,5 z" fill="#a83b36"/></marker>
                      <marker id="clear-arrow-cold" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto"><path d="M0,0 L4.5,2.5 L0,5 z" fill="#385b85"/></marker>
                </defs>

                <path d="M240 245 H290" class="clear-pipe clear-hot" marker-end="url(#clear-arrow-hot)"/>
                <path d="M290 350 H240" class="clear-pipe clear-cold" marker-end="url(#clear-arrow-cold)"/>
                <path d="M490 300 H560" class="clear-pipe clear-hot" marker-end="url(#clear-arrow-hot)"/>
                <path d="M490 380 H560" class="clear-pipe clear-cold" marker-end="url(#clear-arrow-cold)"/>
                <path d="M720 300 H780 V300 H900" class="clear-pipe clear-hot" marker-end="url(#clear-arrow-hot)"/>
                <path d="M900 425 H760 V390 H720" class="clear-pipe clear-cold" marker-end="url(#clear-arrow-cold)"/>
                <path d="M490 220 H520 V100 H560" class="clear-pipe clear-dhw"/>
                <path d="M490 250 H540 V160 H560" class="clear-pipe clear-dhw"/>

                <rect x="40" y="170" width="200" height="240" rx="10" class="clear-box"/>
                <text x="140" y="205" text-anchor="middle" class="clear-title">AUSSENEINHEIT</text>
                <text x="140" y="228" text-anchor="middle" class="clear-label">{escape(snapshot.model)}</text>
                <circle cx="140" cy="285" r="34" fill="none" stroke="{'#a83b36' if compressor_active else '#b9c2cc'}" stroke-width="8"/>
                <path d="M140 251 L151 285 L140 319 L129 285 Z" fill="{'#a83b36' if compressor_active else '#b9c2cc'}"/>
                <text x="140" y="345" text-anchor="middle" class="clear-state">Verdichter {"aktiv" if compressor_active else "aus / bereit"}</text>
                <text x="95" y="375" text-anchor="middle" class="clear-label">LÜFTER 1</text>
                <text x="95" y="395" text-anchor="middle" class="clear-value">{escape(value("Außenlüfter 1"))}</text>
                <text x="185" y="375" text-anchor="middle" class="clear-label">LÜFTER 2</text>
                <text x="185" y="395" text-anchor="middle" class="clear-value">{escape(value("Außenlüfter 2"))}</text>

                <rect x="290" y="190" width="200" height="220" rx="10" class="clear-box"/>
                <text x="390" y="225" text-anchor="middle" class="clear-title">INNENEINHEIT</text>
                <circle cx="350" cy="285" r="25" class="clear-sensor"/>
                <path d="M337 285 Q350 266 363 285 Q350 304 337 285" fill="none" stroke="#17202a" stroke-width="3"/>
                <text x="350" y="330" text-anchor="middle" class="clear-state">Pumpe {escape(value("Inneneinheit Pumpe"))}</text>
                <path d="M430 255 L418 280 H428 L421 306 L445 273 H433 Z" fill="{'#c98b4a' if rod_ready else '#b9c2cc'}"/>
                <text x="430" y="335" text-anchor="middle" class="clear-label">HEIZSTAB</text>
                <text x="430" y="353" text-anchor="middle" class="clear-state">{"bereit / heizt nicht" if rod_ready else "gesperrt"}</text>

                <rect x="560" y="250" width="160" height="180" rx="10" class="clear-buffer"/>
                <text x="640" y="285" text-anchor="middle" class="clear-title">PUFFERSPEICHER</text>
                <path d="M585 345 C680 315 680 375 585 355 C680 335 680 395 585 375" fill="none" stroke="#f7fafc" stroke-width="6" stroke-linecap="round"/>
                <text x="640" y="410" text-anchor="middle" class="clear-value">{escape(value("Pufferspeicher"))}</text>

                <rect x="560" y="40" width="160" height="180" rx="10" class="clear-buffer"/>
                <path d="M585 135 C680 105 680 165 585 145 C680 125 680 185 585 165" fill="none" stroke="#f7fafc" stroke-width="6" stroke-linecap="round"/>
                <text x="640" y="75" text-anchor="middle" class="clear-title" style="font-size:12px">WARMWASSER</text>
                <text x="640" y="94" text-anchor="middle" class="clear-title" style="font-size:12px">SPEICHER</text>
                <text x="640" y="195" text-anchor="middle" class="clear-value">{escape(value("Warmwasser"))}</text>
                <circle cx="780" cy="120" r="18" fill="#fff7ed" stroke="#c98b4a" stroke-width="3"/>
                <path d="M772 120 Q780 110 788 120 Q780 130 772 120" fill="none" stroke="#c98b4a" stroke-width="2"/>
                <path d="M720 80 H780 V180 H720" class="clear-pipe clear-dhw"/>
                <text x="780" y="215" text-anchor="middle" class="clear-label" style="font-size:10px">WARMWASSER-ZIRKULATION</text>
                <text x="780" y="232" text-anchor="middle" class="clear-state">{escape(value("Warmwasser-Zirkulation"))}</text>

                <circle cx="780" cy="300" r="25" class="clear-sensor"/>
                <path d="M767 300 Q780 281 793 300 Q780 319 767 300" fill="none" stroke="#17202a" stroke-width="3"/>
                <text x="780" y="345" text-anchor="middle" class="clear-label">HEIZKREISPUMPE</text>
                <text x="780" y="364" text-anchor="middle" class="clear-value">{escape(value("Heizkreis 1 Pumpe"))}</text>

                <path d="M900 300 H1080 V325 H900 V350 H1080 V375 H900 V400 H1080 V425 H900" class="clear-floor clear-floor-hot"/>
                <path d="M900 425 H1080" class="clear-floor clear-floor-cold"/>
                <text x="990" y="270" text-anchor="middle" class="clear-title" style="font-size:12px">FUSSBODENHEIZUNG</text>
                <text x="990" y="288" text-anchor="middle" class="clear-value">Vorlauf {escape(value("Heizkreis 1 Vorlauf"))}</text>
                <text x="1100" y="450" text-anchor="middle" class="clear-label">HEIZKREIS-RÜCKLAUF</text>
                <text x="1100" y="470" text-anchor="middle" class="clear-state">kein separater Viessmann-Sensor</text>
            </svg>
        </div>
        '''
        render_embedded_html(schema, 620)


def render_viessmann_component_schema(snapshot: object) -> None:
        rows = {
                (row["feature"], row["property"]): row
                for row in feature_values(snapshot)
        }

        def feature(feature_name: str, property_name: str) -> str:
                row = rows.get((feature_name, property_name))
                if not row or not row["value"]:
                        return "nicht verfügbar"
                value_text = str(row["value"])
                return value_text.replace("celsius", "°C").replace("percent", "%")

        compressor_state = feature("heating.compressors.0", "phase")
        compressor_active = str(feature("heating.compressors.0", "active")).lower() == "true"
        compressor_display = f"aktiv ({compressor_state})" if compressor_active else f"bereit ({compressor_state})"
        schema = f'''
        <style>
            html, body {{ margin: 0; background: #f7fafc; }}
            .component-schema-wrap {{ background: #f7fafc; padding: 12px; overflow-x: auto; }}
            .component-schema {{ display: block; width: 100%; max-width: 100%; }}
            .component-pipe {{ fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 7; }}
            .component-hot {{ stroke: #a83b36; }} .component-cold {{ stroke: #385b85; }}
            .component-box {{ fill: #fff; stroke: #17202a; stroke-width: 2; }}
            .component-label, .component-value, .component-title {{ font-family: sans-serif; paint-order: stroke fill; stroke: #f7fafc; stroke-width: 5px; stroke-linejoin: round; }}
            .component-label {{ fill: #52606d; font-size: 12px; }}
            .component-value {{ fill: #17202a; font-size: 15px; font-weight: 700; }}
            .component-title {{ fill: #17202a; font-size: 14px; font-weight: 800; letter-spacing: .8px; }}
            .component-info {{ fill: #fff; stroke: #17202a; stroke-width: 3; }}
            .component-gauge {{ fill: #fff; stroke: #17202a; stroke-width: 2; }}
        </style>
        <div class="component-schema-wrap">
            <svg class="component-schema" viewBox="0 0 1400 520" role="img" aria-label="Vollständiges Viessmann Komponentenbild mit Außen- und Inneneinheit">
                <defs>
                    <marker id="component-arrow-hot" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto"><path d="M0,0 L4.5,2.5 L0,5 z" fill="#a83b36"/></marker>
                    <marker id="component-arrow-cold" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto"><path d="M0,0 L4.5,2.5 L0,5 z" fill="#385b85"/></marker>
                </defs>
                <path d="M220 80 H1080" class="component-pipe component-hot" marker-end="url(#component-arrow-hot)"/>
                <path d="M1080 360 H220" class="component-pipe component-cold" marker-end="url(#component-arrow-cold)"/>
                <path d="M220 80 V160 H300 V300 H220" class="component-pipe component-hot"/>
                <path d="M220 300 V360" class="component-pipe component-cold"/>
                <path d="M520 80 V150 H680 V80" class="component-pipe component-hot"/>
                <path d="M680 80 V180 H520 V300" class="component-pipe component-cold"/>
                <path d="M680 80 H820 V160 H900" class="component-pipe component-hot"/>
                <path d="M900 300 H820 V360 H680" class="component-pipe component-cold"/>
                <path d="M1080 80 H1120 V150 H1180" class="component-pipe component-hot"/>
                <path d="M1180 350 H1120 V360 H1080" class="component-pipe component-cold"/>

                <text x="115" y="35" text-anchor="middle" class="component-title">AUSSENEINHEIT</text>
                <circle cx="75" cy="105" r="28" class="component-info"/>
                <path d="M61 105 Q75 82 89 105 Q75 128 61 105" fill="none" stroke="#17202a" stroke-width="4"/>
                <text x="75" y="150" text-anchor="middle" class="component-label">LÜFTER 1</text>
                <text x="75" y="169" text-anchor="middle" class="component-value">{escape(feature("heating.primaryCircuit.fans.0.current", "value"))}</text>
                <circle cx="75" cy="220" r="28" class="component-info"/>
                <path d="M61 220 Q75 197 89 220 Q75 243 61 220" fill="none" stroke="#17202a" stroke-width="4"/>
                <text x="75" y="265" text-anchor="middle" class="component-label">LÜFTER 2</text>
                <text x="75" y="284" text-anchor="middle" class="component-value">{escape(feature("heating.primaryCircuit.fans.1.current", "value"))}</text>
                <rect x="170" y="105" width="55" height="180" class="component-box"/>
                <path d="M178 125 H217 M178 145 H217 M178 165 H217 M178 185 H217 M178 205 H217 M178 225 H217 M178 245 H217" stroke="#a4adb8" stroke-width="3"/>
                <text x="198" y="320" text-anchor="middle" class="component-label">AUSSENLUFT</text>
                <text x="198" y="339" text-anchor="middle" class="component-value">{escape(feature("heating.sensors.temperature.outside", "value"))}</text>

                <rect x="390" y="165" width="130" height="110" rx="8" class="component-box"/>
                <circle cx="455" cy="220" r="30" class="component-info"/>
                <path d="M438 220 L455 195 L472 220 L455 245 Z" fill="{'#a83b36' if compressor_active else '#b9c2cc'}"/>
                <text x="455" y="305" text-anchor="middle" class="component-title">VERDICHTER</text>
                <text x="455" y="325" text-anchor="middle" class="component-label">{escape(compressor_display)}</text>
                <text x="455" y="345" text-anchor="middle" class="component-value">{escape(feature("heating.compressors.0.sensors.pressure.inlet", "value"))}</text>

                <circle cx="610" cy="80" r="18" class="component-info"/><text x="610" y="87" text-anchor="middle" class="component-title" style="font-size:16px">i</text>
                <text x="610" y="45" text-anchor="middle" class="component-value">{escape(feature("heating.compressors.0.sensors.temperature.outlet", "value"))}</text>
                <rect x="640" y="48" width="80" height="40" class="component-box"/><text x="680" y="74" text-anchor="middle" class="component-value">{escape(feature("heating.compressors.0.speed.current", "value"))}</text>
                <circle cx="760" cy="80" r="18" class="component-info"/><text x="760" y="87" text-anchor="middle" class="component-title" style="font-size:16px">i</text>
                <text x="760" y="45" text-anchor="middle" class="component-value">{escape(feature("heating.compressors.0.sensors.temperature.motorChamber", "value"))}</text>

                <circle cx="1000" cy="360" r="24" class="component-gauge"/><path d="M987 360 Q1000 342 1013 360 Q1000 378 987 360" fill="none" stroke="#17202a" stroke-width="3"/>
                <text x="1000" y="405" text-anchor="middle" class="component-label">PRIMÄRPUMPE</text>
                <text x="1000" y="425" text-anchor="middle" class="component-value">{escape(feature("heating.boiler.pumps.internal.current", "value"))}</text>
                <circle cx="920" cy="170" r="24" class="component-gauge"/><text x="920" y="178" text-anchor="middle" class="component-title" style="font-size:16px">≈</text>
                <text x="920" y="215" text-anchor="middle" class="component-value">{escape(feature("heating.compressors.0.sensors.pressure.inlet", "value"))}</text>
                <text x="920" y="235" text-anchor="middle" class="component-label">DRUCK EINTRITT</text>
                <circle cx="920" cy="280" r="24" class="component-gauge"/><text x="920" y="288" text-anchor="middle" class="component-title" style="font-size:16px">≈</text>
                <text x="920" y="325" text-anchor="middle" class="component-value">{escape(feature("heating.compressors.0.sensors.temperature.inlet", "value"))}</text>
                <text x="920" y="345" text-anchor="middle" class="component-label">TEMPERATUR EINTRITT</text>

                <rect x="1180" y="150" width="180" height="200" rx="10" class="component-box"/>
                <text x="1270" y="180" text-anchor="middle" class="component-title">INNENEINHEIT</text>
                <circle cx="1230" cy="225" r="22" class="component-info"/>
                <path d="M1218 225 Q1230 208 1242 225 Q1230 242 1218 225" fill="none" stroke="#17202a" stroke-width="3"/>
                <text x="1230" y="265" text-anchor="middle" class="component-label">INTERNE PUMPE</text>
                <text x="1230" y="284" text-anchor="middle" class="component-value">{escape(feature("heating.boiler.pumps.internal.current", "value"))}</text>
                <path d="M1305 205 L1294 230 H1304 L1298 254 L1320 222 H1310 Z" fill="#c98b4a"/>
                <text x="1307" y="275" text-anchor="middle" class="component-label">HEIZSTAB</text>
                <text x="1307" y="294" text-anchor="middle" class="component-label">bereit / aus</text>
                <text x="1270" y="325" text-anchor="middle" class="component-label">Vorlauf {escape(feature("heating.circuits.0.sensors.temperature.supply", "value"))}</text>
            </svg>
        </div>
        '''
        render_embedded_html(schema, 500)


def render_heat_pump_kpis(snapshot: object, database_path: str) -> None:
        def raw_value(features: dict[str, object], feature_name: str, property_name: str) -> object:
            for feature in features.get("data", []):
                if not isinstance(feature, dict) or feature.get("feature") != feature_name:
                    continue
                properties = feature.get("properties", {})
                property_data = properties.get(property_name) if isinstance(properties, dict) else None
                if isinstance(property_data, dict):
                    value = property_data.get("value")
                    return value.get("value") if isinstance(value, dict) else value
                return property_data
            return None

        history = get_viessmann_feature_history(database_path, 24)
        samples = [item["features"] for item in history if isinstance(item.get("features"), dict)]

        def current(feature_name: str, property_name: str) -> object:
            return raw_value(snapshot.features, feature_name, property_name)

        def numbers(feature_name: str, property_name: str) -> list[float]:
            values = []
            for features in samples:
                value = raw_value(features, feature_name, property_name)
                if isinstance(value, (int, float)):
                    values.append(float(value))
            return values

        def delta(feature_name: str, property_name: str) -> str:
            values = numbers(feature_name, property_name)
            return "nicht verfügbar" if len(values) < 2 else f"{max(0.0, values[-1] - values[0]):.1f}"

        def fmt(value: object, unit: str = "") -> str:
            if value is None:
                return "nicht verfügbar"
            if isinstance(value, float):
                return f"{value:.1f} {unit}".strip()
            return f"{value} {unit}".strip()

        active_samples = [
            bool(raw_value(features, "heating.compressors.0", "active"))
            for features in samples
        ]
        active_ratio = sum(active_samples) / len(active_samples) if active_samples else None
        observed_hours = 24.0
        if len(history) >= 2:
            first = datetime.fromisoformat(str(history[0]["recorded_at"]).replace("Z", "+00:00"))
            last = datetime.fromisoformat(str(history[-1]["recorded_at"]).replace("Z", "+00:00"))
            observed_hours = max(0.0, (last - first).total_seconds() / 3600)
        supplied_energy = sum(
            float(raw_value(snapshot.features, feature_name, "currentDay") or 0)
            for feature_name in (
                "heating.power.consumption.summary.heating",
                "heating.power.consumption.summary.dhw",
            )
        )
        produced_energy = sum(
            float(raw_value(snapshot.features, feature_name, "currentDay") or 0)
            for feature_name in (
                "heating.heat.production.summary.heating",
                "heating.heat.production.summary.dhw",
            )
        )
        energy_ratio = produced_energy / supplied_energy if supplied_energy > 0 else None
        energy_ratio_display = (
            f"{energy_ratio:.2f}x"
            if energy_ratio is not None
            else f"n/a ({supplied_energy:.1f} kWh zugeführt)"
        )
        starts_24h = numbers("heating.compressors.0.statistics", "starts")
        hours_24h = numbers("heating.compressors.0.statistics", "hours")
        starts_delta = max(0.0, starts_24h[-1] - starts_24h[0]) if len(starts_24h) >= 2 else None
        hours_delta = max(0.0, hours_24h[-1] - hours_24h[0]) if len(hours_24h) >= 2 else None
        average_cycle = hours_delta * 60 / starts_delta if starts_delta and hours_delta is not None else None
        return_temperature = current("heating.sensors.temperature.return", "value")
        secondary_supply_temperature = current("heating.secondaryCircuit.sensors.temperature.supply", "value")
        temperature_spread = (
            float(secondary_supply_temperature) - float(return_temperature)
            if isinstance(secondary_supply_temperature, (int, float)) and isinstance(return_temperature, (int, float))
            else None
        )
        operating_mode = str(current("heating.secondaryCircuit.operation.state", "currentValue") or "nicht verfügbar")
        operating_mode = {"standby": "Bereitschaft", "heating": "Heizen", "dhw": "Warmwasser"}.get(operating_mode, operating_mode)
        kpis = [
            ("Verdichterstarts letzte 24h", delta("heating.compressors.0.statistics", "starts"), ""),
            ("Verdichterstarts gesamt", fmt(current("heating.compressors.0.statistics", "starts"), ""), ""),
            ("Verdichterlaufzeit letzte 24h", delta("heating.compressors.0.statistics", "hours"), "h"),
            ("Verdichterlaufzeit gesamt", fmt(current("heating.compressors.0.statistics", "hours"), "h"), ""),
            ("Außeneinheit aktiv letzte 24h", fmt(active_ratio * 100 if active_ratio is not None else None, "%"), ""),
            ("Außeneinheit aktiv im Beobachtungsfenster", fmt(active_ratio * observed_hours if active_ratio is not None else None, "h"), ""),
            ("Ø Verdichterlaufzeit je Start", fmt(average_cycle, "min"), ""),
            ("Außenlüfter 1 aktuell", fmt(current("heating.primaryCircuit.fans.0.current", "value"), "%"), ""),
            ("Außenlüfter 2 aktuell", fmt(current("heating.primaryCircuit.fans.1.current", "value"), "%"), ""),
            ("Außentemperatur", fmt(current("heating.sensors.temperature.outside", "value"), "°C"), ""),
            ("Heizkreis-Vorlauf", fmt(current("heating.circuits.0.sensors.temperature.supply", "value"), "°C"), ""),
            ("Anlagenrücklauf", fmt(current("heating.sensors.temperature.return", "value"), "°C"), ""),
            ("Pufferspeicher", fmt(current("heating.bufferCylinder.sensors.temperature.main", "value"), "°C"), ""),
            ("Warmwasserspeicher", fmt(current("heating.dhw.sensors.temperature.dhwCylinder", "value"), "°C"), ""),
            ("Interne Pumpe", fmt(current("heating.boiler.pumps.internal.current", "value"), "%"), ""),
            ("Heizstab für Heizen heute", fmt(current("heating.heatingRod.power.consumption.summary.heating", "currentDay"), "kWh"), ""),
            ("Heizstab für Warmwasser heute", fmt(current("heating.heatingRod.power.consumption.summary.dhw", "currentDay"), "kWh"), ""),
            ("Energie zugeführt heute", fmt(supplied_energy, "kWh"), ""),
            ("Energie erzeugt heute", fmt(produced_energy, "kWh"), ""),
            ("Energie-Ratio erzeugt / zugeführt heute", energy_ratio_display, ""),
            ("SPF Heizen", fmt(current("heating.spf.heating", "value"), ""), ""),
            ("SPF Warmwasser", fmt(current("heating.spf.dhw", "value"), ""), ""),
            ("SPF Gesamt", fmt(current("heating.spf.total", "value"), ""), ""),
            ("Sekundärkreis-Spreizung", fmt(temperature_spread, "°C"), ""),
            ("Elektrische Leistung aktuell", fmt(current("heating.power.consumption.current", "value"), "kW"), ""),
            ("Wärmeleistung aktuell", fmt(current("heating.heat.production.current", "value"), "kW"), ""),
            ("Betriebsmodus", operating_mode, ""),
            ("Abtauung", "aktiv" if bool(current("heating.outdoor.defrosting", "active")) else "inaktiv", ""),
            ("Verdichterstatus", f"aktiv ({current('heating.compressors.0', 'phase')})" if bool(current("heating.compressors.0", "active")) else f"bereit ({current('heating.compressors.0', 'phase')})", ""),
        ]
        st.markdown("### Wärmepumpen-Kennzahlen")
        st.caption("Aktuelle Werte und, soweit Snapshots vorhanden sind, berechnete Werte der letzten 24 Stunden.")
        for start in range(0, len(kpis), 3):
            columns = st.columns(3)
            for column, (label, value, _) in zip(columns, kpis[start:start + 3]):
                with column:
                    st.metric(label, value)


def render_heating_curve(snapshot: object) -> None:
        values = {
            (row["feature"], row["property"]): row["value"]
            for row in feature_values(snapshot)
        }
        slope = values.get(("heating.circuits.0.heating.curve", "slope"))
        shift = values.get(("heating.circuits.0.heating.curve", "shift"))
        try:
            slope = float(slope) if slope is not None else None
            shift = float(shift) if shift is not None else None
        except (TypeError, ValueError):
            slope = None
            shift = None
        st.markdown("### Aktuelle Heizkurve")
        st.caption("Heizkreis 1, direkt aus dem aktuellen Viessmann-Snapshot.")
        columns = st.columns(2)
        with columns[0]:
            st.metric("Steigung", f"{slope} " if slope is not None else "nicht verfügbar")
        with columns[1]:
            st.metric("Niveau / Shift", f"{shift} °C" if shift is not None else "nicht verfügbar")
        if isinstance(slope, (int, float)) and isinstance(shift, (int, float)):
            outdoor_temperatures = list(range(-20, 26, 5))
            supply_targets = [
                max(10.0, min(40.0, 20.0 + float(slope) * (20.0 - outdoor_temperature) + float(shift)))
                for outdoor_temperature in outdoor_temperatures
            ]
            chart_points = []
            x_step = 416 / max(1, len(supply_targets) - 1)
            for index, supply_target in enumerate(supply_targets):
                x_position = 58 + index * x_step
                y_position = 205 - (supply_target - 10.0) / 30.0 * 165
                chart_points.append((x_position, y_position, outdoor_temperatures[index], supply_target))
            curve_path = " ".join(
                f"{'M' if index == 0 else 'L'} {x_position:.1f} {y_position:.1f}"
                for index, (x_position, y_position, _, _) in enumerate(chart_points)
            )
            curve_markers = "".join(
                f'<circle cx="{x_position:.1f}" cy="{y_position:.1f}" r="4" fill="#a83b36"/>'
                for x_position, y_position, _, _ in chart_points
            )
            curve_labels = "".join(
                f'<text x="{x_position:.1f}" y="235" text-anchor="middle">{outdoor_temperature}°</text>'
                for x_position, _, outdoor_temperature, _ in chart_points
            )
            curve_markup = f'''
            <style>
              body {{ margin: 0; background: #f3f7fb; font-family: sans-serif; }}
              svg {{ display: block; width: 100%; height: 260px; }}
              .axis {{ stroke: #829ab1; stroke-width: 1.5; }}
              .grid {{ stroke: #d9e2ec; stroke-width: 1; }}
              text {{ fill: #486581; font-size: 12px; }}
              .axis-title {{ fill: #243b53; font-size: 13px; font-weight: 700; }}
              .curve {{ fill: none; stroke: #a83b36; stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }}
            </style>
            <svg viewBox="0 0 520 260" role="img" aria-label="Heizkurve: Vorlauf-Solltemperatur in Abhängigkeit von der Außentemperatur">
              <line x1="58" y1="40" x2="58" y2="205" class="axis"/>
              <line x1="58" y1="205" x2="474" y2="205" class="axis"/>
              <line x1="58" y1="40" x2="474" y2="40" class="grid"/>
              <line x1="58" y1="122" x2="474" y2="122" class="grid"/>
              <line x1="58" y1="205" x2="474" y2="205" class="grid"/>
              <text x="48" y="45" text-anchor="end">40°C</text>
              <text x="48" y="127" text-anchor="end">25°C</text>
              <text x="48" y="210" text-anchor="end">10°C</text>
              <path d="{curve_path}" class="curve"/>
              {curve_markers}
              {curve_labels}
              <text x="265" y="258" text-anchor="middle" class="axis-title">Außentemperatur</text>
              <text x="14" y="125" text-anchor="middle" transform="rotate(-90 14 125)" class="axis-title">Vorlauf-Soll</text>
            </svg>
            '''
            render_embedded_html(curve_markup, 275)


def render_heat_pump_report(snapshot: object, history: list[dict[str, object]]) -> None:
    st.markdown('<div class="level-heading">Wärmepumpenbericht</div>', unsafe_allow_html=True)
    sections = report_sections(snapshot)
    latest_read = history[0]["recorded_at"] if history else "unbekannt"
    st.caption(f"{snapshot.model} | Geräte-ID {snapshot.device_id} | Read-only | Gelesen am: {latest_read}")

    render_heat_pump_kpis(snapshot, str(DATABASE_PATH))
    st.markdown("### Anlagenbild")
    st.caption("Schematische Live-Ansicht. Rot = Vorlauf, Blau = hydraulischer Rücklauf; Viessmann liefert hierfür keinen separaten Heizkreis-Sensor.")
    render_clear_heat_pump_schema(snapshot)
    st.markdown("### Viessmann-Komponentenbild")
    st.caption("Originalnahe Komponentenansicht mit den verfügbaren Viessmann-Livewerten.")
    render_viessmann_component_schema(snapshot)
    render_heating_curve(snapshot)

    status_columns = st.columns(4)
    with status_columns[0]:
        st.metric("Status", "Online" if snapshot.online else "Offline")
    with status_columns[1]:
        st.metric("Datenpunkte", sum(len(rows) for rows in sections.values()))
    with status_columns[2]:
        st.metric("Historische Snapshots", len(history))
    with status_columns[3]:
        st.metric("Bereiche", len(sections))

    for section_name, rows in sections.items():
        with st.expander(section_name, expanded=section_name in {"Status & Betrieb", "Temperaturen & Sensoren"}):
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Messwert": row["name"], "Wert": row["value"] or "-", "Einheit": row["unit"]}
                        for row in rows
                    ]
                ),
                hide_index=True,
                width="stretch",
                column_config={
                    "Messwert": st.column_config.TextColumn("Messwert", width="large"),
                    "Wert": st.column_config.TextColumn("Wert", width="medium"),
                    "Einheit": st.column_config.TextColumn("Einheit", width="small"),
                },
            )

    with st.container(border=True):
        st.markdown("### Historie")
        st.caption("Jeder erfolgreiche read-only Abruf wird als unveränderter Snapshot gespeichert.")
        if history:
            st.dataframe(
                pd.DataFrame(history),
                hide_index=True,
                width="stretch",
                column_config={
                    "recorded_at": "Zeitpunkt",
                    "device_id": "Gerät",
                    "model": "Modell",
                    "online": "Online",
                    "feature_count": "Datenpunkte",
                },
            )
        else:
            st.info("Noch keine historischen Snapshots vorhanden.")

    with st.expander("Technische Rohdaten"):
        st.json(snapshot.features)


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
        options=("Home", "Raumdetail", "Raumbericht", "Alle Diagramme", "Wärmepumpe", "Wetter", "Einstellungen"),
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

if function_choice == "Home":
    st.session_state["show_all_graphs"] = False
    st.session_state["show_settings"] = False
    st.session_state["view"] = "overview"
    st.query_params.clear()
elif function_choice == "Raumdetail":
    st.session_state["show_all_graphs"] = False
    st.session_state["show_settings"] = False
    st.session_state["view"] = "detail"
    room_name = st.session_state.get("selected_room", "")
    st.query_params.clear()
    st.query_params["room"] = room_name
    st.query_params["view"] = "detail"
elif function_choice == "Alle Diagramme":
    st.session_state["show_all_graphs"] = True
    st.session_state["show_settings"] = False
    st.session_state["view"] = "overview"
elif function_choice == "Raumbericht":
    st.session_state["show_all_graphs"] = False
    st.session_state["show_settings"] = False
    st.session_state["view"] = "report"
    st.query_params.clear()
    st.query_params["view"] = "report"
elif function_choice == "Wärmepumpe":
    st.session_state["show_all_graphs"] = False
    st.session_state["show_settings"] = False
    st.session_state["view"] = "heat-pump-report"
elif function_choice == "Wetter":
    st.session_state["show_all_graphs"] = False
    st.session_state["show_settings"] = False
    st.session_state["view"] = "weather-report"
else:
    st.session_state["show_all_graphs"] = False
    st.session_state["show_settings"] = True
    st.session_state["view"] = "overview"

@st.dialog("Einstellungen")
def settings_dialog() -> None:
    homematic_tab, viessmann_tab = st.tabs(["Homematic IP", "Viessmann"])
    with homematic_tab:
        if st.button("Homematic IP Geraete neu einlesen", type="primary"):
            try:
                st.session_state["device_home"] = load_home()
                st.success("Homematic IP Geraete wurden neu eingelesen.")
            except HomematicProviderError as error:
                st.error(str(error))

        if st.button("Geraetehierarchie anzeigen"):
            if st.session_state.get("device_home") is None:
                try:
                    st.session_state["device_home"] = load_home()
                except HomematicProviderError as error:
                    st.error(str(error))
            st.session_state["show_device_hierarchy"] = not st.session_state.get(
                "show_device_hierarchy", False
            )

        if st.session_state.get("show_device_hierarchy", False):
            device_home = st.session_state.get("device_home")
            if device_home is None:
                st.info("Lese zuerst die Homematic IP Geraete ein.")
            else:
                render_device_hierarchy(device_home)

    with viessmann_tab:
        st.caption("Read-only access. Credentials are held in this browser session only.")
        with st.form("viessmann-settings-form"):
            username = st.text_input("Viessmann account email", key="viessmann-username")
            password = st.text_input("Viessmann account password", type="password", key="viessmann-password")
            client_id = st.text_input("Viessmann API client ID", key="viessmann-client-id")
            token_file = st.text_input(
                "Token file",
                value="data/vicare_token.json",
                key="viessmann-token-file",
            )
            load_viessmann = st.form_submit_button("Viessmann-Daten einlesen", type="primary")
            load_heat_pump = st.form_submit_button("Wärmepumpe read-only einlesen")

        if load_viessmann or load_heat_pump:
            try:
                client = load_client(username, password, client_id, token_file)
                if load_viessmann:
                    inventory = read_inventory(client)
                    save_viessmann_snapshots(DATABASE_PATH, inventory)
                    st.session_state["viessmann_inventory"] = inventory
                    st.success("Viessmann-Daten wurden read-only eingelesen und archiviert.")
                if load_heat_pump:
                    heat_pumps = read_heat_pumps(client)
                    st.session_state["viessmann_heat_pumps"] = heat_pumps
                    save_viessmann_snapshots(
                        DATABASE_PATH,
                        [
                            {
                                "id": heat_pump.device_id,
                                "model": heat_pump.model,
                                "online": heat_pump.online,
                                "features": heat_pump.features,
                            }
                            for heat_pump in heat_pumps
                        ],
                    )
                    st.success("Wärmepumpen-Daten wurden read-only eingelesen.")
            except ViessmannProviderError as error:
                st.error(str(error))

        if not st.session_state.get("viessmann_heat_pumps"):
            archived_heat_pumps = heat_pump_snapshots_from_inventory(
                get_latest_viessmann_snapshots(DATABASE_PATH)
            )
            if archived_heat_pumps:
                st.session_state["viessmann_heat_pumps"] = archived_heat_pumps

        if st.session_state.get("viessmann_inventory"):
            render_viessmann_inventory(st.session_state["viessmann_inventory"])
        if st.session_state.get("viessmann_heat_pumps"):
            st.info("Wärmepumpenbericht geladen. Öffne ihn über die Navigation.")


if st.session_state.get("show_settings", False):
    settings_dialog()

if function_choice == "Wetter":
    render_weather_page()
    st.stop()

if function_choice == "Wärmepumpe":
    snapshot_history = get_viessmann_snapshot_history(DATABASE_PATH)
    archived_heat_pumps = heat_pump_snapshots_from_inventory(
        get_latest_viessmann_snapshots(DATABASE_PATH)
    )
    if archived_heat_pumps:
        render_heat_pump_page(archived_heat_pumps[0], snapshot_history, render_heat_pump_report)
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
