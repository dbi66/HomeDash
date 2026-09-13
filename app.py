from pathlib import Path
import os
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from src.database import get_latest_readings, get_room_history, save_readings
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
                flex-wrap: nowrap;
                gap: 0.5rem;
                max-width: calc(100vw - 1.5rem) !important;
                width: calc(100vw - 1.5rem) !important;
            }

            [data-testid="stColumn"] {
                flex: 0 0 calc(50% - 0.25rem);
                min-width: 0;
                width: calc(50% - 0.25rem) !important;
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

room_names = sorted({str(reading["room_name"]) for reading in readings})
query_room = st.query_params.get("room")
selected_room = query_room or st.session_state.get("selected_room", room_names[0])
if selected_room not in room_names:
    selected_room = room_names[0]
st.session_state["selected_room"] = selected_room


def render_history(room_name: str) -> None:
    st.markdown(
        f'<div style="color:#102a43;font-size:1.35rem;font-weight:750;margin:0.5rem 0 0.25rem;">History: {escape(room_name)}</div>',
        unsafe_allow_html=True,
    )
    history_window = st.selectbox(
        "Time range",
        options=(24, 168, 720),
        format_func=lambda hours: {24: "Last 24 hours", 168: "Last 7 days", 720: "Last 30 days"}[hours],
    )
    history = get_room_history(DATABASE_PATH, room_name, history_window)
    if len(history) < 2:
        st.info("Not enough snapshots for a trend yet. Keep the collector running to build history.")
        return

    history_frame = pd.DataFrame(history)
    history_frame["recorded_at"] = pd.to_datetime(history_frame["recorded_at"], utc=True)
    history_frame = history_frame.set_index("recorded_at")
    time_axis = alt.Axis(format="%H:%M", title=None)
    chart_columns = st.columns(2)
    with chart_columns[0]:
        temperature_data = history_frame.reset_index().melt(
            id_vars="recorded_at",
            value_vars=["current_temperature", "target_temperature"],
            var_name="series",
            value_name="temperature",
        )
        temperature_chart = alt.Chart(temperature_data).mark_line().encode(
            x=alt.X("recorded_at:T", axis=time_axis),
            y=alt.Y("temperature:Q", title="Temperature (C)"),
            color=alt.Color("series:N", title=None),
            tooltip=[
                alt.Tooltip("recorded_at:T", title="Time", format="%H:%M"),
                alt.Tooltip("series:N", title="Series"),
                alt.Tooltip("temperature:Q", title="C", format=".1f"),
            ],
        ).properties(height=220)
        st.altair_chart(temperature_chart, use_container_width=True)
    with chart_columns[1]:
        percent_data = history_frame.reset_index().melt(
            id_vars="recorded_at",
            value_vars=["valve_position", "humidity"],
            var_name="series",
            value_name="percent",
        )
        percent_chart = alt.Chart(percent_data).mark_line().encode(
            x=alt.X("recorded_at:T", axis=time_axis),
            y=alt.Y("percent:Q", title="Percent"),
            color=alt.Color("series:N", title=None),
            tooltip=[
                alt.Tooltip("recorded_at:T", title="Time", format="%H:%M"),
                alt.Tooltip("series:N", title="Series"),
                alt.Tooltip("percent:Q", title="%", format=".0f"),
            ],
        ).properties(height=220)
        st.altair_chart(percent_chart, use_container_width=True)


with st.container(border=True):
    history_room = st.selectbox("Selected room", room_names, index=room_names.index(selected_room))
    if history_room != selected_room:
        selected_room = history_room
        st.session_state["selected_room"] = selected_room
        st.query_params["room"] = selected_room
        st.rerun()
    else:
        st.query_params["room"] = selected_room
    render_history(selected_room)

def valve_color(valve_position: float) -> str:
    if valve_position <= 0:
        return "#dbeafe"
    intensity = min(1.0, valve_position / 100)
    start = (245, 158, 11)
    end = (220, 38, 38)
    color = tuple(round(start[index] + (end[index] - start[index]) * intensity) for index in range(3))
    return "rgb({}, {}, {})".format(*color)


def render_room_tiles(level_readings: list[dict[str, object]]) -> None:
    columns = st.columns(min(4, len(level_readings)))
    for index, reading in enumerate(level_readings):
        room_name = escape(str(reading["room_name"]))
        valve_position = float(reading["valve_position"])
        status = "Heating" if valve_position > 0 else "Idle"
        selection = "Selected" if str(reading["room_name"]) == selected_room else status
        tile_label = (
            f"**{room_name}**\n\n"
            f"{float(reading['current_temperature']):.1f} C  |  Target {float(reading['target_temperature']):.1f} C\n\n"
            f"Humidity {float(reading['humidity']):.0f}%  |  Valve {valve_position:.0f}%  |  {selection}"
        )
        with columns[index % len(columns)]:
            if st.button(
                tile_label,
                key=f"room-tile-{reading['room_name']}",
                width="stretch",
                type="secondary",
            ):
                st.session_state["selected_room"] = str(reading["room_name"])
                st.query_params["room"] = str(reading["room_name"])
                st.rerun()


grouped_readings = group_readings_by_level(readings)
for level in (UPSTAIRS, BASE_LEVEL, UNASSIGNED):
    level_readings = grouped_readings.get(level, [])
    if level_readings:
        st.markdown(
            f'<div style="color:#102a43;font-size:1.35rem;font-weight:750;margin:1.75rem 0 0.25rem;">{escape(level)}</div>',
            unsafe_allow_html=True,
        )
        render_room_tiles(level_readings)

with st.expander("Show latest readings table"):
    st.dataframe(
        readings,
        hide_index=True,
        width="stretch",
        column_config={
            "room_name": "Room",
            "current_temperature": st.column_config.NumberColumn("Current (C)", format="%.1f"),
            "target_temperature": st.column_config.NumberColumn("Target (C)", format="%.1f"),
            "humidity": st.column_config.NumberColumn("Humidity (%)", format="%.0f"),
            "valve_position": st.column_config.NumberColumn("Valve (%)", format="%.0f"),
            "recorded_at": "Recorded at",
        },
    )
