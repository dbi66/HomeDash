from pathlib import Path
import os
from html import escape

import streamlit as st

from src.database import get_latest_readings, save_readings
from src.history import save_home_snapshot
from src.hmip_provider import CONFIG_PATH, HomematicProviderError, load_home, get_room_readings as get_hmip_readings, map_room_readings
from src.mock_provider import get_room_readings
from src.room_layout import BASE_LEVEL, UNASSIGNED, UPSTAIRS, group_readings_by_level


DATABASE_PATH = Path(__file__).resolve().parent / "data" / "heating_data.db"

st.set_page_config(page_title="HomeClimate Dashboard", page_icon=":house:", layout="wide")

st.markdown(
    """
    <style>
        .stApp {
            background: #f3f7fb;
        }

        .dashboard-header {
            padding: 0.75rem 0 1rem;
        }

        .dashboard-header h1 {
            color: #102a43;
            font-size: 2.1rem;
            letter-spacing: 0;
            margin-bottom: 0.25rem;
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
            margin: 1.75rem 0 0.25rem;
        }

        .room-card {
            border: 1px solid rgba(16, 42, 67, 0.12);
            border-radius: 10px;
            box-shadow: 0 8px 20px rgba(16, 42, 67, 0.08);
            min-height: 188px;
            padding: 1.1rem;
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
            .room-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


PROVIDER = os.getenv("HOMEDASH_PROVIDER", "homematic" if CONFIG_PATH.exists() else "mock").lower()


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


st.markdown(
    f'<div class="dashboard-header"><h1>HomeClimate Dashboard</h1><p>Data provider: {escape(PROVIDER)}</p></div>',
    unsafe_allow_html=True,
)

if st.button("Refresh readings", type="primary"):
    try:
        if PROVIDER == "homematic":
            home = load_home()
            save_readings(DATABASE_PATH, map_room_readings(home))
            snapshot_count = save_home_snapshot(DATABASE_PATH, home)
            st.caption(f"Archived {snapshot_count} Homematic objects.")
        else:
            save_readings(DATABASE_PATH, collect_readings())
        st.success("Readings updated.")
    except HomematicProviderError as error:
        st.error(str(error))

try:
    readings = load_readings()
except HomematicProviderError as error:
    st.error(str(error))
    st.info("Set HOMEDASH_PROVIDER=mock to run without Homematic IP hardware.")
    readings = get_latest_readings(DATABASE_PATH)

if not readings:
    st.warning("No room readings are available yet.")
    st.stop()

def valve_color(valve_position: float) -> str:
    if valve_position <= 0:
        return "#dbeafe"
    intensity = min(1.0, valve_position / 100)
    start = (245, 158, 11)
    end = (220, 38, 38)
    color = tuple(round(start[index] + (end[index] - start[index]) * intensity) for index in range(3))
    return "rgb({}, {}, {})".format(*color)


def render_room_cards(level_readings: list[dict[str, object]]) -> None:
    cards = []
    for reading in level_readings:
        room_name = escape(str(reading["room_name"]))
        valve_position = float(reading["valve_position"])
        status = "Heating" if valve_position > 0 else "Idle"
        cards.append(
            f'<article class="room-card" style="background: {valve_color(valve_position)};">'
            f'<div class="room-card__top"><span class="room-card__name">{room_name}</span>'
            f'<span class="room-card__status">{status}</span></div>'
            f'<div class="room-card__reading"><span class="room-card__temperature">'
            f'{float(reading["current_temperature"]):.1f} C</span><span class="room-card__target">'
            f'Target {float(reading["target_temperature"]):.1f} C</span></div>'
            f'<div class="room-card__meta"><span>Humidity <strong>{float(reading["humidity"]):.0f}%</strong></span>'
            f'<span>Valve <strong>{valve_position:.0f}%</strong></span></div></article>'
        )
    st.markdown(f'<section class="room-grid">{"".join(cards)}</section>', unsafe_allow_html=True)


grouped_readings = group_readings_by_level(readings)
for level in (UPSTAIRS, BASE_LEVEL, UNASSIGNED):
    level_readings = grouped_readings.get(level, [])
    if level_readings:
        st.markdown(
            f'<div style="color:#102a43;font-size:1.35rem;font-weight:750;margin:1.75rem 0 0.25rem;">{escape(level)}</div>',
            unsafe_allow_html=True,
        )
        render_room_cards(level_readings)

with st.expander("Show latest readings table"):
    st.dataframe(
        readings,
        hide_index=True,
        use_container_width=True,
        column_config={
            "room_name": "Room",
            "current_temperature": st.column_config.NumberColumn("Current (C)", format="%.1f"),
            "target_temperature": st.column_config.NumberColumn("Target (C)", format="%.1f"),
            "humidity": st.column_config.NumberColumn("Humidity (%)", format="%.0f"),
            "valve_position": st.column_config.NumberColumn("Valve (%)", format="%.0f"),
            "recorded_at": "Recorded at",
        },
    )
