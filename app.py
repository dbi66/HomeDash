from pathlib import Path
import os

import streamlit as st

from src.database import get_latest_readings, save_readings
from src.hmip_provider import CONFIG_PATH, HomematicProviderError, get_room_readings as get_hmip_readings
from src.mock_provider import get_room_readings


DATABASE_PATH = Path(__file__).resolve().parent / "data" / "heating_data.db"

st.set_page_config(page_title="HomeClimate Dashboard", page_icon=":house:", layout="wide")


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


st.title("HomeClimate Dashboard")
st.caption(f"Data provider: {PROVIDER}")

if st.button("Refresh readings", type="primary"):
    try:
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

columns = st.columns(len(readings))
for column, reading in zip(columns, readings):
    with column:
        st.metric(
            reading["room_name"],
            f'{reading["current_temperature"]:.1f} C',
            f'Target {reading["target_temperature"]:.1f} C',
        )
        st.write(f'Humidity: {reading["humidity"]:.0f}%')
        st.write(f'Valve: {reading["valve_position"]:.0f}%')

st.subheader("Latest readings")
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
