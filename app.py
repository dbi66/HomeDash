import re
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from src.database import get_latest_readings, get_room_events, get_room_history, get_room_trends, save_readings, save_viessmann_snapshots
from src.config import DATABASE_PATH, PROVIDER
from src.history import save_home_snapshot
from src.hmip_provider import HomematicProviderError, load_home, get_room_readings as get_hmip_readings, map_room_readings
from src.mock_provider import get_room_readings
from src.room_layout import BASE_LEVEL, UNASSIGNED, UPSTAIRS, group_readings_by_level
from src.viessmann_provider import ViessmannProviderError, read_all_information


st.set_page_config(page_title="HomeClimate Dashboard", page_icon=":house:", layout="wide")

st.markdown(
    """
    <style>
        .stApp {
            background: #f3f7fb;
        }

        .dashboard-header {
            padding: 0.35rem 0 0.5rem;
        }

        .dashboard-header h1 {
            color: #102a43;
            font-size: 2.1rem;
            letter-spacing: 0;
            margin-bottom: 0.25rem;
        }

        [class*="st-key-refresh-button"] button {
            background: #ffffff;
            border: 1px solid #bcccdc;
            border-radius: 8px;
            color: #102a43;
            min-height: 42px !important;
            padding: 0.45rem 0.8rem !important;
        }

        [class*="st-key-refresh-button"] button p {
            font-size: 0.8rem;
            font-weight: 700;
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
            margin: 1rem 0 0.35rem;
        }

        .room-card {
            border: 1px solid rgba(16, 42, 67, 0.12);
            border-radius: 10px;
            box-shadow: 0 8px 20px rgba(16, 42, 67, 0.08);
            min-height: 154px;
            padding: 0.9rem;
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

                .device-tree {
                    background: #eef5fb;
                    border: 1px solid #c9d8e6;
                    border-radius: 10px;
                    margin-top: 0.75rem;
                    padding: 1rem;
                }

                .device-tree__root {
                    align-items: center;
                    background: #102a43;
                    border-radius: 8px;
                    color: #ffffff;
                    display: flex;
                    font-weight: 700;
                    gap: 0.6rem;
                    padding: 0.7rem 0.85rem;
                }

                .device-tree__branch {
                    border-left: 2px solid #9fb3c8;
                    margin: 0.5rem 0 0 0.9rem;
                    padding-left: 1rem;
                }

                .device-node {
                    background: #ffffff;
                    border: 1px solid #d9e2ec;
                    border-radius: 8px;
                    margin: 0.55rem 0;
                    padding: 0.7rem;
                }

                .device-node__title {
                    color: #102a43;
                    font-size: 0.9rem;
                    font-weight: 700;
                }

                .device-node__model {
                    color: #627d98;
                    font-size: 0.75rem;
                    margin-left: 0.35rem;
                }

                .channel-chip {
                    background: #dbeafe;
                    border-radius: 999px;
                    color: #243b53;
                    display: inline-block;
                    font-size: 0.7rem;
                    margin: 0.45rem 0.35rem 0 0;
                    padding: 0.25rem 0.5rem;
                }

                [class*="st-key-settings-button"] button p {
                    font-size: 1.45rem;
                    line-height: 1;
                }

                [class*="st-key-overview-room-"] button p:first-child {
                    color: #102a43;
                    font-size: 1.35rem;
                    font-weight: 800;
                    line-height: 1.05;
                }

                [class*="st-key-overview-room-"] button p:nth-child(2) {
                    color: #102a43;
                    font-size: 1.8rem;
                    font-weight: 800;
                    line-height: 1.05;
                }

                [class*="st-key-function-navigation"] {
                    min-width: 190px;
                }
    </style>
    """,
    unsafe_allow_html=True,
)


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


def render_device_hierarchy(home: object) -> None:
    devices = sorted(
        getattr(home, "devices", []),
        key=lambda device: str(getattr(device, "label", "")).lower(),
    )
    nodes = []
    for device in devices:
        label = str(getattr(device, "label", "Unnamed device"))
        model = str(getattr(device, "modelType", "Unknown model"))
        channels = sorted(
            getattr(device, "functionalChannels", []),
            key=lambda item: int(getattr(item, "index", 0)),
        )
        chips = []
        for channel in channels:
            channel_type = escape(str(getattr(channel, "functionalChannelType", "Unknown channel")))
            channel_label = escape(str(getattr(channel, "label", "")))
            channel_index = escape(str(getattr(channel, "index", "?")))
            title = f"{channel_index}: {channel_type}"
            if channel_label:
                title = f"{title} | {channel_label}"
            chips.append(f'<span class="channel-chip">{title}</span>')
        channel_html = "".join(chips) or '<span class="channel-chip">No channels</span>'
        nodes.append(
            f'<div class="device-node"><div class="device-node__title">{escape(label)}'
            f'<span class="device-node__model">{escape(model)}</span></div>{channel_html}</div>'
        )
    tree = (
        f'<div class="device-tree"><div class="device-tree__root">HomeClimate'
        f'<span class="device-tree__model">{len(devices)} devices</span></div>'
        f'<div class="device-tree__branch">{"".join(nodes)}</div></div>'
    )
    st.markdown(tree, unsafe_allow_html=True)


def render_viessmann_inventory(inventory: list[dict[str, object]]) -> None:
    st.caption(f"{len(inventory)} Viessmann device(s)")
    for device in inventory:
        features = device.get("features", {})
        feature_rows = features.get("data", []) if isinstance(features, dict) else []
        with st.expander(f"{device['model']} | {device['id']} | {'online' if device['online'] else 'offline'}"):
            if not feature_rows:
                st.json(features)
                continue
            rows = []
            for feature in feature_rows:
                if isinstance(feature, dict):
                    rows.append(
                        {
                            "feature": feature.get("feature", ""),
                            "properties": ", ".join(sorted(feature.get("properties", {}).keys())),
                        }
                    )
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            else:
                st.json(features)


header_actions = st.columns([6, 2, 3])
with header_actions[0]:
    st.markdown(
        '<div class="dashboard-header"><h1>HomeClimate Dashboard</h1></div>',
        unsafe_allow_html=True,
    )
with header_actions[1]:
    if st.button("Refresh", key="refresh-button", help="Read current Homematic IP values", width="stretch"):
        try:
            if PROVIDER == "homematic":
                home = load_home()
                save_readings(DATABASE_PATH, map_room_readings(home))
                snapshot_count = save_home_snapshot(DATABASE_PATH, home)
                st.caption(f"Archived {snapshot_count} Homematic objects.")
            else:
                save_readings(DATABASE_PATH, collect_readings())
            st.success("Readings updated.")
            st.rerun()
        except HomematicProviderError as error:
            st.error(str(error))
with header_actions[2]:
    route_hint = "Raumdetail" if st.query_params.get("view") == "detail" else "Home"
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
        options=("Home", "Raumdetail", "Alle Diagramme", "Einstellungen"),
        key="function-navigation",
        label_visibility="collapsed",
    )
previous_choice = st.session_state.get("navigation-last")
st.session_state["navigation-last"] = function_choice
if function_choice == "Home":
    st.session_state["show_all_graphs"] = False
    if function_choice != previous_choice or st.session_state.get("show_settings", False) or st.query_params:
        st.session_state["show_settings"] = False
        st.session_state["view"] = "overview"
        st.query_params.clear()
        st.rerun()
elif function_choice == "Raumdetail":
    st.session_state["show_all_graphs"] = False
    st.session_state["show_settings"] = False
    if function_choice != previous_choice and not st.query_params.get("room"):
        st.session_state["view"] = "detail"
        st.query_params["room"] = st.session_state.get("selected_room", "")
        st.query_params["view"] = "detail"
        st.rerun()
elif function_choice == "Alle Diagramme":
    st.session_state["show_all_graphs"] = True
    st.session_state["show_settings"] = False
else:
    st.session_state["show_all_graphs"] = False
    st.session_state["show_settings"] = True

@st.dialog("Einstellungen")
def settings_dialog() -> None:
    homematic_tab, viessmann_tab = st.tabs(["Homematic IP", "Viessmann"])
    with homematic_tab:
        if st.button("Homematic IP Geraete neu einlesen", type="primary"):
            try:
                st.session_state["device_home"] = load_home()
                st.success("Homematic IP Geraete wurden neu eingelesen.")
            except HomematicProviderError as error:
                st.error(str(error))

        if st.button("Geraetehierarchie anzeigen"):
            if st.session_state.get("device_home") is None:
                try:
                    st.session_state["device_home"] = load_home()
                except HomematicProviderError as error:
                    st.error(str(error))
            st.session_state["show_device_hierarchy"] = not st.session_state.get(
                "show_device_hierarchy", False
            )

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
            token_file = st.text_input(
                "Token file",
                value="data/vicare_token.json",
                key="viessmann-token-file",
            )
            load_viessmann = st.form_submit_button("Viessmann-Daten einlesen", type="primary")

        if load_viessmann:
            try:
                inventory = read_all_information(username, password, client_id, token_file)
                save_viessmann_snapshots(DATABASE_PATH, inventory)
                st.session_state["viessmann_inventory"] = inventory
                st.success("Viessmann-Daten wurden read-only eingelesen und archiviert.")
            except ViessmannProviderError as error:
                st.error(str(error))

        if st.session_state.get("viessmann_inventory"):
            render_viessmann_inventory(st.session_state["viessmann_inventory"])


if st.session_state.get("show_settings", False):
    settings_dialog()

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
page = pending_view or st.session_state.get("view", st.query_params.get("view", "detail" if query_room else "overview"))
selected_room = pending_room or query_room or st.session_state.get("selected_room", room_names[0])
if selected_room not in room_names:
    selected_room = room_names[0]
st.session_state["selected_room"] = selected_room


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


def render_overview() -> None:
    grouped = group_readings_by_level(readings)
    for level in (UPSTAIRS, BASE_LEVEL, UNASSIGNED):
        level_readings = grouped.get(level, [])
        if not level_readings:
            continue
        st.markdown(f'<div class="level-heading">{escape(level)}</div>', unsafe_allow_html=True)
        columns = st.columns(min(4, len(level_readings)))
        for index, reading in enumerate(level_readings):
            room_name = str(reading["room_name"])
            valve = float(reading["valve_position"])
            trends = get_room_trends(DATABASE_PATH, room_name)
            label = (
                f"**{room_name}**\n\n"
                f"{float(reading['current_temperature']):.1f} C {colored_trend(trends['temperature'])}  |  {float(reading['humidity']):.0f}% {colored_trend(trends['humidity'])}\n\n"
                f"Target {float(reading['target_temperature']):.1f} C  |  Valve {valve_meter(valve)} {valve:.0f}%"
            )
            with columns[index % len(columns)]:
                if st.button(label, key=f"overview-room-{room_name}", width="stretch"):
                    st.session_state["selected_room"] = room_name
                    st.session_state["pending-navigation"] = "Raumdetail"
                    st.session_state["pending-room"] = room_name
                    st.session_state["pending-view"] = "detail"
                    st.query_params.clear()
                    st.query_params.update({"room": room_name, "view": "detail"})
                    st.rerun()
    st.caption(f"Data provider: {PROVIDER}")


def render_overview_graphs() -> None:
    st.markdown('<div class="level-heading">Alle Diagramme</div>', unsafe_allow_html=True)
    hours = st.selectbox(
        "History range",
        options=(24, 168, 720),
        format_func=lambda value: {24: "Last 24 hours", 168: "Last 7 days", 720: "Last 30 days"}[value],
        key="overview-all-graphs-window",
    )
    graph_columns = st.columns(2)
    for index, room_name in enumerate(room_names):
        history = get_room_history(DATABASE_PATH, room_name, hours)
        if len(history) < 2:
            continue
        with graph_columns[index % 2]:
            render_climate_chart(pd.DataFrame(history), room_name, 180, "Fixed range")


def render_climate_chart(
    history_frame: pd.DataFrame,
    title: str,
    height: int,
    scale_mode: str,
) -> None:
    history_frame["recorded_at"] = pd.to_datetime(history_frame["recorded_at"], utc=True)
    temperature_scale = alt.Scale(domain=[10, 30]) if scale_mode == "Fixed range" else alt.Scale(zero=False)
    percent_scale = alt.Scale(domain=[0, 100]) if scale_mode == "Fixed range" else alt.Scale(zero=False)
    time_axis = alt.Axis(format="%H:%M", title=None)
    current = history_frame[["recorded_at", "current_temperature"]].rename(columns={"current_temperature": "value"})
    target = history_frame[["recorded_at", "target_temperature"]].rename(columns={"target_temperature": "value"})
    humidity = history_frame[["recorded_at", "humidity"]].rename(columns={"humidity": "value"})
    valve = history_frame[["recorded_at", "valve_position"]].rename(columns={"valve_position": "value"})
    current["series"] = "IST"
    target["series"] = "Ziel"
    humidity["series"] = "Feuchtigkeit"
    valve["series"] = "Ventil"
    chart_slug = re.sub(r"[^a-zA-Z0-9_-]", "-", title)
    selected_series = []
    render_chart_legend()
    selector_columns = st.columns(4)
    for column, series_name in zip(selector_columns, ("IST", "Ziel", "Feuchtigkeit", "Ventil")):
        with column:
            if st.checkbox(series_name, value=True, key=f"chart-line-{chart_slug}-{series_name}"):
                selected_series.append(series_name)
    if not selected_series:
        st.info("Select at least one line.")
        return
    current = current[current["series"].isin(selected_series)]
    target = target[target["series"].isin(selected_series)]
    humidity = humidity[humidity["series"].isin(selected_series)]
    valve = valve[valve["series"].isin(selected_series)]
    temperature_axis = alt.Axis(title="Temperature (C)", orient="left", titleColor="#0b7285")
    percentage_axis = alt.Axis(title="Humidity / valve (%)", orient="right", titleColor="#7c3aed")
    label_axis = alt.Axis(title=None, labels=False, ticks=False, domain=False)

    def line(data: pd.DataFrame, color: str, dash=None, scale=None, axis=None, points=False):
        mark = {"color": color, "strokeWidth": 2}
        if dash:
            mark["strokeDash"] = dash
        if points:
            mark["point"] = {"size": 18, "filled": True}
        return alt.Chart(data).mark_line(**mark).encode(
            x=alt.X("recorded_at:T", axis=time_axis, scale=alt.Scale(padding=20)),
            y=alt.Y("value:Q", scale=scale, axis=axis),
            color=alt.Color(
                "series:N",
                scale=alt.Scale(
                    domain=["IST", "Ziel", "Feuchtigkeit", "Ventil"],
                    range=["#d9480f", "#64748b", "#7c3aed", "#e03131"],
                ),
                legend=None,
            ),
        )

    def endpoint_label(data: pd.DataFrame, color: str, fmt: str, scale=None, dy=0):
        return (
            alt.Chart(data)
            .transform_window(
                rank="rank()",
                sort=[alt.SortField("recorded_at", order="descending")],
            )
            .transform_filter(alt.datum.rank == 1)
            .mark_text(align="left", dx=10, dy=dy, fontSize=10, color=color)
            .encode(
                x=alt.X("recorded_at:T", scale=alt.Scale(padding=20)),
                y=alt.Y("value:Q", scale=scale, axis=label_axis),
                text=alt.Text("value:Q", format=fmt),
            )
        )

    layers = []
    if not current.empty:
        layers.extend([line(current, "#d9480f", scale=temperature_scale, axis=temperature_axis, points=len(history_frame) <= 72), endpoint_label(current, "#d9480f", ".1f", temperature_scale, dy=-8)])
    if not target.empty:
        layers.extend([line(target, "#94a3b8", dash=[6, 3], scale=temperature_scale, axis=label_axis), endpoint_label(target, "#64748b", ".1f", temperature_scale, dy=10)])
    if not humidity.empty:
        layers.extend([line(humidity, "#7c3aed", dash=[2, 2], scale=percent_scale, axis=percentage_axis), endpoint_label(humidity, "#7c3aed", ".0f", percent_scale, dy=-8)])
    if not valve.empty:
        layers.extend([line(valve, "#e03131", dash=[2, 2], scale=percent_scale, axis=label_axis), endpoint_label(valve, "#e03131", ".0f", percent_scale, dy=10)])

    chart = alt.layer(*layers).resolve_scale(y="independent").properties(
        height=height,
        title=title,
        padding={"right": 70, "left": 20},
    )
    st.altair_chart(chart, use_container_width=True)


def render_chart_legend() -> None:
    st.markdown(
        '<div style="color:#486581;font-size:0.78rem;margin:0.35rem 0 0.75rem;">'
        '<strong>Legende:</strong> '
        '<span style="color:#d9480f;font-weight:700">&#9644; IST-Temperatur</span> &nbsp; '
        '<span style="color:#64748b">- - Zieltemperatur</span> &nbsp; '
        '<span style="color:#7c3aed">·· Feuchtigkeit</span> &nbsp; '
        '<span style="color:#e03131">·· Ventil</span>'
        '</div>',
        unsafe_allow_html=True,
    )


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
    scale_mode = st.selectbox(
        "Chart scale",
        options=("Fixed range", "Fit data"),
        key=f"chart-scale-{room_name}",
        help="Temperature defaults to 10-30 C. Humidity and valve use 0-100%.",
    )
    history = get_room_history(DATABASE_PATH, room_name, history_window)
    if len(history) < 2:
        st.info("Not enough snapshots for a trend yet. Keep the collector running to build history.")
        return

    history_frame = pd.DataFrame(history)
    render_climate_chart(history_frame, room_name, 360, scale_mode)


def render_compact_chart(room_name: str, hours: int) -> None:
    history = get_room_history(DATABASE_PATH, room_name, hours)
    if len(history) < 2:
        st.caption(f"{room_name}: not enough data")
        return
    render_climate_chart(pd.DataFrame(history), room_name, 180, "Fixed range")


if page == "overview":
    if st.session_state.get("show_all_graphs", False):
        render_overview_graphs()
    render_overview()
    st.stop()


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
    if st.button("Event log", key="event-log-button", width="stretch"):
        st.session_state["show_event_log"] = not st.session_state.get("show_event_log", False)
        st.rerun()
    if st.session_state.get("show_event_log", False):
        events = get_room_events(DATABASE_PATH, selected_room)
        if not events:
            st.caption("No valve or target-temperature events recorded yet.")
        else:
            for event in events:
                st.write(f"{event['recorded_at']}  |  {event['message']}")

if st.session_state.get("show_all_graphs", False):
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
                render_compact_chart(room_name, all_graph_hours)

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
            color = valve_color(valve_position)
            widget_slug = room_widget_slug(str(reading["room_name"]))
            st.markdown(
                f"<style>.st-key-overview-room-{widget_slug} button {{ background: {color}; }} "
                f".st-key-overview-room-{widget_slug} button:hover {{ background: {color}; filter: brightness(0.96); }}</style>",
                unsafe_allow_html=True,
            )
            if st.button(
                tile_label,
                key=f"room-tile-{reading['room_name']}",
                width="stretch",
                type="secondary",
            ):
                st.session_state["selected_room"] = str(reading["room_name"])
                st.session_state["pending-navigation"] = "Raumdetail"
                st.session_state["pending-room"] = str(reading["room_name"])
                st.session_state["pending-view"] = "detail"
                st.query_params.clear()
                st.query_params.update({"room": str(reading["room_name"]), "view": "detail"})
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

st.caption(f"Data provider: {PROVIDER}")
