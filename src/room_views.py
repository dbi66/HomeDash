from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from src.database import get_room_events
from src.dashboard_views import render_compact_chart, render_history, render_room_tiles, render_valve_status_table
from src.room_layout import BASE_LEVEL, UNASSIGNED, UPSTAIRS, group_readings_by_level


def render_room_detail_view(readings: list[dict[str, object]], room_names: list[str], selected_room: str, database_path: str) -> None:
    with st.container(border=True):
        history_room = st.selectbox("Selected room", room_names, index=room_names.index(selected_room))
        if history_room != selected_room:
            selected_room = history_room
            st.session_state["selected_room"] = selected_room
            st.query_params["room"] = selected_room
            st.rerun()
        else:
            st.query_params["room"] = selected_room
        render_history(selected_room, database_path)
        selected_reading = next(
            reading for reading in readings if str(reading["room_name"]) == selected_room
        )
        st.markdown("### Ventilstatus")
        render_valve_status_table([selected_reading])
        if st.button("Event log", key="event-log-button", width="stretch"):
            st.session_state["show_event_log"] = not st.session_state.get("show_event_log", False)
            st.rerun()
        if st.session_state.get("show_event_log", False):
            events = get_room_events(database_path, selected_room)
            if not events:
                st.caption("No valve or target-temperature events recorded yet.")
            else:
                for event in events:
                    st.write(f"{event['recorded_at']}  |  {event['message']}")


def render_room_overview_view(readings: list[dict[str, object]], room_names: list[str], database_path: str, provider: str) -> None:
    if not readings:
        return
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

    st.caption(f"Data provider: {provider}")


def render_all_graphs(room_names: list[str], database_path: str) -> None:
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
                render_compact_chart(room_name, database_path, all_graph_hours)
