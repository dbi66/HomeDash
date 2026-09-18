import math
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
    st.altair_chart(chart, width="stretch")


def render_spider_chart(
    readings: list[dict[str, object]],
    value_key: str,
    title: str,
    domain: tuple[float, float],
    color: str,
    key: str,
) -> None:
    if not readings:
        st.info(f"Keine Daten für {title} verfügbar.")
        return

    minimum, maximum = domain
    span = maximum - minimum
    angle_step = 2 * math.pi / len(readings)
    polygon = []
    labels = []
    spokes = []
    rings = []
    for index, reading in enumerate(readings):
        angle = index * angle_step - math.pi / 2
        value = float(reading[value_key])
        normalized = max(0.0, min(1.0, (value - minimum) / span))
        polygon.append(
            {
                "x": normalized * math.cos(angle),
                "y": normalized * math.sin(angle),
                "series": "value",
                "order": index,
            }
        )
        labels.append(
            {
                "x": 1.12 * math.cos(angle),
                "y": 1.12 * math.sin(angle),
                "room_name": str(reading["room_name"]),
            }
        )
        spokes.extend(
            [
                {"x": 0.0, "y": 0.0, "spoke": index},
                {"x": math.cos(angle), "y": math.sin(angle), "spoke": index, "order": 1},
            ]
        )
        spokes[-2]["order"] = 0

    polygon.append(polygon[0])
    for ring_level in (0.25, 0.5, 0.75, 1.0):
        for point_index in range(41):
            angle = 2 * math.pi * point_index / 40 - math.pi / 2
            rings.append(
                {
                    "x": ring_level * math.cos(angle),
                    "y": ring_level * math.sin(angle),
                    "ring": ring_level,
                    "order": point_index,
                }
            )

    chart_data = pd.DataFrame(polygon)
    ring_data = pd.DataFrame(rings)
    spoke_data = pd.DataFrame(spokes)
    label_data = pd.DataFrame(labels)
    extent = alt.Scale(domain=[-1.25, 1.25])
    chart = alt.layer(
        alt.Chart(ring_data).mark_line(color="#d9e2ec", strokeWidth=1).encode(
            x=alt.X("x:Q", scale=extent, axis=None),
            y=alt.Y("y:Q", scale=extent, axis=None),
            detail="ring:N",
            order="order:Q",
        ),
        alt.Chart(spoke_data).mark_line(color="#d9e2ec", strokeWidth=1).encode(
            x=alt.X("x:Q", scale=extent, axis=None),
            y=alt.Y("y:Q", scale=extent, axis=None),
            detail="spoke:N",
            order="order:Q",
        ),
        alt.Chart(chart_data).mark_line(color=color, strokeWidth=3).encode(
            x=alt.X("x:Q", scale=extent, axis=None),
            y=alt.Y("y:Q", scale=extent, axis=None),
            order="order:Q",
        ),
        alt.Chart(chart_data).mark_point(color=color, filled=True, size=45).encode(
            x=alt.X("x:Q", scale=extent, axis=None),
            y=alt.Y("y:Q", scale=extent, axis=None),
        ),
        alt.Chart(label_data).mark_text(fontSize=11, color="#334e68").encode(
            x=alt.X("x:Q", scale=extent, axis=None),
            y=alt.Y("y:Q", scale=extent, axis=None),
            text="room_name:N",
        ),
    ).properties(title=title, width="container", height=420, background="#ffffff").configure(
        background="#ffffff",
        title=alt.TitleConfig(color="#102a43", fontSize=16, anchor="start"),
        view=alt.ViewConfig(stroke="#d9e2ec", fill="#ffffff"),
    )
    st.altair_chart(chart, width="stretch", key=key)


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
