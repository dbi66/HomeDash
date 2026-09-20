from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PAGES = ("Home", "Raumdetail", "Raumbericht", "Alle Diagramme", "Wärmepumpe", "Wetter", "Einstellungen")


@dataclass(frozen=True)
class NavigationState:
    page: str
    room: str | None = None
    show_all_graphs: bool = False
    show_settings: bool = False


def apply_navigation(page: str, session_state: Any, query_params: Any) -> NavigationState:
    state = NavigationState(
        page=page,
        room=session_state.get("selected_room"),
        show_all_graphs=page == "Alle Diagramme",
        show_settings=page == "Einstellungen",
    )
    session_state["show_all_graphs"] = state.show_all_graphs
    session_state["show_settings"] = state.show_settings
    session_state["view"] = {
        "Home": "overview",
        "Raumdetail": "detail",
        "Raumbericht": "report",
        "Alle Diagramme": "overview",
        "Wärmepumpe": "heat-pump-report",
        "Wetter": "weather-report",
        "Einstellungen": "overview",
    }[page]
    if page == "Home":
        query_params.clear()
    elif page == "Raumdetail":
        query_params.clear()
        if state.room:
            query_params.update({"room": state.room, "view": "detail"})
    elif page == "Raumbericht":
        query_params.clear()
        query_params["view"] = "report"
    return state
