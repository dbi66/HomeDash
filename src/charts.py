import re
from typing import Optional

import altair as alt
import pandas as pd
import streamlit as st


SERIES_NAMES = ("IST", "Ziel", "Feuchtigkeit", "Ventil")
SERIES_COLORS = {
    "IST": "#d9480f",
    "Ziel": "#64748b",
    "Feuchtigkeit": "#7c3aed",
    "Ventil": "#e03131",
}


def render_climate_chart(
    history_frame: pd.DataFrame,
    title: str,
    height: int,
    scale_mode: str,
    key_prefix: str,
) -> None:
    history_frame = history_frame.copy()
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
    selected_series = _selected_series(title, key_prefix)
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

    layers = []
    if not current.empty:
        layers.extend([
            _line(current, "#d9480f", scale=temperature_scale, axis=temperature_axis, points=len(history_frame) <= 72, time_axis=time_axis),
            _endpoint_label(current, "#d9480f", ".1f", temperature_scale, label_axis, dy=-8),
        ])
    if not target.empty:
        layers.extend([
            _line(target, "#94a3b8", dash=[6, 3], scale=temperature_scale, axis=label_axis, time_axis=time_axis),
            _endpoint_label(target, "#64748b", ".1f", temperature_scale, label_axis, dy=10),
        ])
    if not humidity.empty:
        layers.extend([
            _line(humidity, "#7c3aed", dash=[2, 2], scale=percent_scale, axis=percentage_axis, time_axis=time_axis),
            _endpoint_label(humidity, "#7c3aed", ".0f", percent_scale, label_axis, dy=-8),
        ])
    if not valve.empty:
        layers.extend([
            _line(valve, "#e03131", dash=[2, 2], scale=percent_scale, axis=label_axis, time_axis=time_axis),
            _endpoint_label(valve, "#e03131", ".0f", percent_scale, label_axis, dy=10),
        ])

    chart = alt.layer(*layers).resolve_scale(y="independent").properties(
        height=height,
        title=title,
        padding={"right": 70, "left": 20},
    )
    st.altair_chart(chart, use_container_width=True)


def _selected_series(title: str, key_prefix: str) -> list[str]:
    chart_slug = re.sub(r"[^a-zA-Z0-9_-]", "-", title)
    selected_series = []
    with st.container(border=True):
        _render_chart_legend()
        selector_columns = st.columns(4)
        for column, series_name in zip(selector_columns, SERIES_NAMES):
            with column:
                if st.checkbox(series_name, value=True, key=f"chart-line-{key_prefix}-{chart_slug}-{series_name}"):
                    selected_series.append(series_name)
    return selected_series


def _line(
    data: pd.DataFrame,
    color: str,
    dash: Optional[list[int]] = None,
    scale: Optional[alt.Scale] = None,
    axis: Optional[alt.Axis] = None,
    points: bool = False,
    time_axis: Optional[alt.Axis] = None,
) -> alt.Chart:
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
                domain=list(SERIES_NAMES),
                range=["#d9480f", "#64748b", "#7c3aed", "#e03131"],
            ),
            legend=None,
        ),
    )


def _endpoint_label(
    data: pd.DataFrame,
    color: str,
    value_format: str,
    scale: Optional[alt.Scale],
    axis: alt.Axis,
    dy: int = 0,
) -> alt.Chart:
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
            y=alt.Y("value:Q", scale=scale, axis=axis),
            text=alt.Text("value:Q", format=value_format),
        )
    )


def _render_chart_legend() -> None:
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
