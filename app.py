from pathlib import Path

import streamlit as st

from src.database import get_latest_readings, save_readings
from src.mock_provider import get_room_readings


DATABASE_PATH = Path(__file__).resolve().parent / "data" / "heating_data.db"

st.set_page_config(page_title="HomeClimate Dashboard", page_icon=":house:", layout="wide")


def load_readings() -> list[dict[str, object]]:
    readings = get_latest_readings(DATABASE_PATH)
    if not readings:
        save_readings(DATABASE_PATH, get_room_readings())
        readings = get_latest_readings(DATABASE_PATH)
    return readings


st.title("HomeClimate Dashboard")
st.caption("Milestone 1 is running with local mock readings. Homematic IP integration comes next.")

if st.button("Refresh mock data", type="primary"):
    save_readings(DATABASE_PATH, get_room_readings())
    st.rerun()

readings = load_readings()

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
