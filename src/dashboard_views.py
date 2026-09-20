import re
from html import escape
from pathlib import Path
from typing import Callable, Optional, Union

import pandas as pd
import streamlit as st

from src.charts import render_climate_chart, render_spider_chart
from src.database import get_room_history, get_room_trends
from src.room_layout import BASE_LEVEL, UNASSIGNED, UPSTAIRS, group_readings_by_level


Reading = dict[str, object]
OpenRoom = Callable[[str], None]


def valve_meter(valve_position: float) -> str:
    filled = round(max(0.0, min(100.0, valve_position)) / 10)
    return "[{}{}]".format("#" * filled, "-" * (10 - filled))


def colored_trend(arrow: str) -> str:
    colors = {
        "↑": "red",
        "↗": "orange",
        "→": "gray",
        "↘": "blue",
        "↓": "blue",
    }
    return f':{colors.get(arrow, "gray")}[' + arrow + "]"


def room_widget_slug(room_name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", room_name)


def _open_room(room_name: str) -> None:
    st.session_state["selected_room"] = room_name
    st.session_state["pending-navigation"] = "Raumdetail"
    st.session_state["pending-room"] = room_name
    st.session_state["pending-view"] = "detail"
    st.query_params.clear()
    st.query_params.update({"room": room_name, "view": "detail"})
    st.rerun()


def _room_label(reading: Reading, trends: Optional[dict[str, str]] = None) -> str:
    room_name = str(reading["room_name"])
    compact_name = room_name if len(room_name) <= 22 else f"{room_name[:19]}…"
    temperature = float(reading["current_temperature"])
    humidity = float(reading["humidity"])
    target = float(reading["target_temperature"])
    valve = float(reading["valve_position"])
    temperature_trend = f" {colored_trend(trends['temperature'])}" if trends else ""
    humidity_trend = f" {colored_trend(trends['humidity'])}" if trends else ""
    short_target = f"Ziel {target:.1f}°"
    short_valve = f"Ventil {valve_meter(valve)} {valve:.0f}%"
    first_line = f"**{escape(compact_name)}**"
    second_line = f"{temperature:.1f} °C{temperature_trend} · {humidity:.0f}%{humidity_trend} · {short_target}"
    third_line = short_valve
    return f"{first_line}  \n{second_line}  \n{third_line}"


def _render_room_button(
    reading: Reading,
    key_prefix: str,
    label: str,
    open_room: OpenRoom,
    background: Optional[str] = None,
) -> None:
    room_name = str(reading["room_name"])
    with st.container():
        if background:
            widget_slug = room_widget_slug(room_name)
            st.markdown(
                f"<style>.st-key-{key_prefix}-{widget_slug} button {{ background: {background} !important; background-color: {background} !important; }} "
                f".st-key-{key_prefix}-{widget_slug} button:hover {{ background: {background} !important; background-color: {background} !important; filter: brightness(0.96); }}</style>",
                unsafe_allow_html=True,
            )
        if st.button(
            label,
            key=f"{key_prefix}-{room_name}",
            width="stretch",
            type="secondary",
        ):
            open_room(room_name)


def render_overview(
    readings: list[Reading], database_path: Union[str, Path], provider: str
) -> None:
    grouped = group_readings_by_level(readings)
    with st.container(key="room-status-grid"):
        for level in (UPSTAIRS, BASE_LEVEL, UNASSIGNED):
            level_readings = grouped.get(level, [])
            if not level_readings:
                continue
            st.markdown(f'<div class="level-heading">{escape(level)}</div>', unsafe_allow_html=True)
            columns = st.columns(min(4, len(level_readings)))
            for index, reading in enumerate(level_readings):
                room_name = str(reading["room_name"])
                trends = get_room_trends(database_path, room_name)
                valve_position = float(reading["valve_position"])
                background = valve_color(valve_position)
                with columns[index % len(columns)]:
                    _render_room_button(
                        reading,
                        key_prefix="overview-room",
                        label=_room_label(reading, trends),
                        open_room=_open_room,
                        background=background,
                    )
    st.caption(f"Data provider: {provider}")


def render_overview_graphs(room_names: list[str], database_path: Union[str, Path]) -> None:
    st.markdown('<div class="level-heading">Alle Diagramme</div>', unsafe_allow_html=True)
    hours = st.selectbox(
        "History range",
        options=(24, 168, 720),
        format_func=lambda value: {24: "Last 24 hours", 168: "Last 7 days", 720: "Last 30 days"}[value],
        key="overview-all-graphs-window",
    )
    graph_columns = st.columns(2)
    for index, room_name in enumerate(room_names):
        history = get_room_history(database_path, room_name, hours)
        if len(history) < 2:
            continue
        with graph_columns[index % 2]:
            render_climate_chart(pd.DataFrame(history), room_name, 180, "Fixed range", "all")


def render_valve_status_table(readings: list[Reading]) -> None:
    report_frame = pd.DataFrame(
        [
            {
                "Raum": reading["room_name"],
                "Ist (C)": reading["current_temperature"],
                "Ziel (C)": reading["target_temperature"],
                "Ventil (%)": reading["valve_position"],
            }
            for reading in readings
        ]
    )
    styled_frame = report_frame.style.apply(
        lambda row: [
            "" for _ in row
        ] if row["Ventil (%)"] <= 0 else [
            "" if column != "Ventil (%)" else f"background-color: {valve_color(float(row['Ventil (%)']))}; color: #102a43; font-weight: 700"
            for column in row.index
        ],
        axis=1,
    )
    st.dataframe(styled_frame, hide_index=True, width="stretch")


def render_room_report(readings: list[Reading]) -> None:
    st.markdown('<div class="level-heading">Raumbericht</div>', unsafe_allow_html=True)
    latest_read = max(
        (str(reading.get("recorded_at", "")) for reading in readings),
        default="unbekannt",
    )
    st.caption(f"Aktuelle Raumwerte im Vergleich. Gelesen am: {latest_read}")
    chart_columns = st.columns(2)
    with chart_columns[0]:
        render_spider_chart(
            readings,
            value_key="current_temperature",
            title="IST-Temperatur (C)",
            domain=(10.0, 30.0),
            color="#d9480f",
            key="room-report-temperature",
        )
    with chart_columns[1]:
        render_spider_chart(
            readings,
            value_key="humidity",
            title="Feuchtigkeit (%)",
            domain=(0.0, 100.0),
            color="#7c3aed",
            key="room-report-humidity",
        )
    st.markdown("### Ventilstatus")
    render_valve_status_table(readings)


def render_history(room_name: str, database_path: Union[str, Path]) -> None:
    st.markdown(
        f'<div style="color:#102a43;font-size:1.35rem;font-weight:750;margin:0.5rem 0 0.25rem;">History: {escape(room_name)}</div>',
        unsafe_allow_html=True,
    )
    history_window = st.selectbox(
        "Time range",
        options=(24, 168, 720),
        format_func=lambda hours: {24: "Last 24 hours", 168: "Last 7 days", 720: "Last 30 days"}[hours],
    )
    scale_mode = st.selectbox(
        "Chart scale",
        options=("Fixed range", "Fit data"),
        key=f"chart-scale-{room_name}",
        help="Temperature defaults to 10-30 C. Humidity and valve use 0-100%.",
    )
    history = get_room_history(database_path, room_name, history_window)
    if len(history) < 2:
        st.info("Not enough snapshots for a trend yet. Keep the collector running to build history.")
        return

    st.caption(f"Letzter Messwert gelesen am: {history[-1]['recorded_at']}")
    render_climate_chart(pd.DataFrame(history), room_name, 360, scale_mode, "detail")


def render_compact_chart(room_name: str, database_path: Union[str, Path], hours: int) -> None:
    history = get_room_history(database_path, room_name, hours)
    if len(history) < 2:
        st.caption(f"{room_name}: not enough data")
        return
    render_climate_chart(pd.DataFrame(history), room_name, 180, "Fixed range", "compact")


def valve_color(valve_position: float) -> str:
    if valve_position <= 0:
        return "#dbeafe"
    intensity = min(1.0, valve_position / 100)
    start = (245, 158, 11)
    end = (220, 38, 38)
    color = tuple(round(start[index] + (end[index] - start[index]) * intensity) for index in range(3))
    return "rgb({}, {}, {})".format(*color)


def render_room_tiles(level_readings: list[Reading]) -> None:
    columns = st.columns(min(4, len(level_readings)))
    for index, reading in enumerate(level_readings):
        valve_position = float(reading["valve_position"])
        background = valve_color(valve_position)
        with columns[index % len(columns)]:
            _render_room_button(
                reading,
                key_prefix="room-tile",
                label=_room_label(reading),
                open_room=_open_room,
                background=background,
            )
