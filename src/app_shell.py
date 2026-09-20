from __future__ import annotations

from html import escape

import streamlit as st

from src.database import get_latest_data_timestamps
from src.display import format_data_age, format_timestamp
from src.navigation import PAGES


def render_app_header(app_name: str, database_path: str) -> str:
    header_actions = st.columns([8, 3])
    with header_actions[0]:
        st.markdown(
            f'<div class="dashboard-header"><h1>{escape(app_name)}</h1></div>',
            unsafe_allow_html=True,
        )
        timestamps = get_latest_data_timestamps(database_path)
        st.caption(
            "Letzte Daten: "
            f"Homematic {format_timestamp(timestamps['homematic'])} ({format_data_age(timestamps['homematic'])}) | "
            f"Viessmann {format_timestamp(timestamps['viessmann'])} ({format_data_age(timestamps['viessmann'])})"
        )
    with header_actions[1]:
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

    st.session_state["navigation-last"] = function_choice
    return function_choice
