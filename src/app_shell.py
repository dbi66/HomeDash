from __future__ import annotations

from html import escape

import streamlit as st

from src.database import get_latest_data_timestamps
from src.display import format_data_age, format_timestamp
from src.navigation import PAGES


def render_app_header(app_name: str, database_path: str) -> str:
    header_actions = st.columns([6, 2, 3])
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
        if st.button(
            "Neu laden",
            key="refresh-button",
            help="Seite neu darstellen; Datenabfragen laufen automatisch im festen Raster.",
            width="stretch",
        ):
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

    timestamps = get_latest_data_timestamps(database_path)
    st.markdown(
        "<div style=\"background:#ffffff;border:1px solid #d9e2ec;border-radius:8px;"
        "color:#486581;font-size:0.85rem;margin:0.25rem 0 1rem;padding:0.5rem 0.75rem;\">"
        "Letzte Daten: "
        f"Homematic {escape(format_timestamp(timestamps['homematic']))} | "
        f"Viessmann {escape(format_timestamp(timestamps['viessmann']))}"
        "</div>",
        unsafe_allow_html=True,
    )
    st.session_state["navigation-last"] = function_choice
    return function_choice
