from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import streamlit as st


HomeLoader = Callable[[], object]
ClientLoader = Callable[..., Any]
InventoryLoader = Callable[[Any], list[dict[str, object]]]
HeatPumpLoader = Callable[[Any], list[Any]]
SnapshotSaver = Callable[[str | Path, list[dict[str, object]]], int]
InventoryRenderer = Callable[[list[dict[str, object]]], None]
HierarchyRenderer = Callable[[object], None]


@st.dialog("Einstellungen")
def render_settings_dialog(
    *,
    database_path: str | Path,
    load_home: HomeLoader,
    load_client: ClientLoader,
    read_inventory: InventoryLoader,
    read_heat_pumps: HeatPumpLoader,
    save_viessmann_snapshots: SnapshotSaver,
    latest_viessmann_snapshots: Callable[[str | Path], list[dict[str, object]]],
    heat_pumps_from_inventory: Callable[[list[dict[str, object]]], list[Any]],
    render_device_hierarchy: HierarchyRenderer,
    render_viessmann_inventory: InventoryRenderer,
    homematic_error: type[Exception],
    viessmann_error: type[Exception],
) -> None:
    homematic_tab, viessmann_tab = st.tabs(["Homematic IP", "Viessmann"])
    with homematic_tab:
        if st.button("Homematic IP Geraete neu einlesen", type="primary"):
            try:
                st.session_state["device_home"] = load_home()
                st.success("Homematic IP Geraete wurden neu eingelesen.")
            except homematic_error as error:
                st.error(str(error))

        if st.button("Geraetehierarchie anzeigen"):
            if st.session_state.get("device_home") is None:
                try:
                    st.session_state["device_home"] = load_home()
                except homematic_error as error:
                    st.error(str(error))
            st.session_state["show_device_hierarchy"] = not st.session_state.get("show_device_hierarchy", False)

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
            token_file = st.text_input("Token file", value="data/vicare_token.json", key="viessmann-token-file")
            load_viessmann = st.form_submit_button("Viessmann-Daten einlesen", type="primary")
            load_heat_pump = st.form_submit_button("Wärmepumpe read-only einlesen")

        if load_viessmann or load_heat_pump:
            try:
                client = load_client(username, password, client_id, token_file)
                if load_viessmann:
                    inventory = read_inventory(client)
                    save_viessmann_snapshots(database_path, inventory)
                    st.session_state["viessmann_inventory"] = inventory
                    st.success("Viessmann-Daten wurden read-only eingelesen und archiviert.")
                if load_heat_pump:
                    heat_pumps = read_heat_pumps(client)
                    st.session_state["viessmann_heat_pumps"] = heat_pumps
                    save_viessmann_snapshots(
                        database_path,
                        [{"id": item.device_id, "model": item.model, "online": item.online, "features": item.features} for item in heat_pumps],
                    )
                    st.success("Wärmepumpen-Daten wurden read-only eingelesen.")
            except viessmann_error as error:
                st.error(str(error))

        if not st.session_state.get("viessmann_heat_pumps"):
            archived_heat_pumps = heat_pumps_from_inventory(latest_viessmann_snapshots(database_path))
            if archived_heat_pumps:
                st.session_state["viessmann_heat_pumps"] = archived_heat_pumps

        if st.session_state.get("viessmann_inventory"):
            render_viessmann_inventory(st.session_state["viessmann_inventory"])
        if st.session_state.get("viessmann_heat_pumps"):
            st.info("Wärmepumpenbericht geladen. Öffne ihn über die Navigation.")
