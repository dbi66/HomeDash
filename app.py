import streamlit as st

from src.app_shell import render_app_header
from src.config import DATABASE_PATH, PROVIDER
from src.dashboard_views import render_overview_graphs, render_room_report
from src.database import (
    get_latest_readings,
    get_latest_viessmann_snapshots,
    get_viessmann_snapshot_history,
    save_readings,
    save_viessmann_snapshots,
)
from src.heat_pump_inventory_view import render_viessmann_inventory
from src.heat_pump_report_view import render_heat_pump_report, render_heat_pump_report_page
from src.hmip_provider import HomematicProviderError, get_room_readings as get_hmip_readings, load_home
from src.home_dashboard import render_home_dashboard as render_home_dashboard_page
from src.mock_provider import get_room_readings
from src.navigation import apply_navigation
from src.room_views import render_all_graphs, render_room_detail_view, render_room_overview_view
from src.settings_view import render_device_hierarchy, render_settings_dialog
from src.ui_theme import apply_app_theme
from src.viessmann_heatpump import heat_pump_snapshots_from_inventory, read_heat_pumps
from src.viessmann_provider import ViessmannProviderError, load_client, read_inventory
from src.weather_view import render_weather_report as render_weather_page


APP_NAME = "HomeClimate Dashboard"

st.set_page_config(page_title=APP_NAME, page_icon=":house:", layout="wide")

apply_app_theme()


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



function_choice = render_app_header(APP_NAME, DATABASE_PATH)
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
page = st.session_state.get("view", st.query_params.get("view", "detail" if query_room else "overview"))
selected_room = query_room or st.session_state.get("selected_room", room_names[0])
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

render_room_detail_view(readings, room_names, selected_room, DATABASE_PATH)

if st.session_state.get("show_all_graphs", False):
    render_all_graphs(room_names, DATABASE_PATH)

render_room_overview_view(readings, room_names, DATABASE_PATH, PROVIDER)
