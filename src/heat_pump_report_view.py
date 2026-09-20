from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from src.config import DATABASE_PATH
from src.database import get_viessmann_feature_history
from src.heat_pump_rendering import (
    render_clear_heat_pump_schema,
    render_heating_curve,
    render_viessmann_component_schema,
)
from src.viessmann_heatpump import report_sections

ReportRenderer = Callable[[Any, list[dict[str, object]]], None]


def render_heat_pump_kpis(snapshot: object, database_path: str) -> None:
    def raw_value(features: dict[str, object], feature_name: str, property_name: str) -> object:
        for feature in features.get("data", []):
            if not isinstance(feature, dict) or feature.get("feature") != feature_name:
                continue
            properties = feature.get("properties", {})
            property_data = properties.get(property_name) if isinstance(properties, dict) else None
            if isinstance(property_data, dict):
                value = property_data.get("value")
                return value.get("value") if isinstance(value, dict) else value
            return property_data
        return None

    history = get_viessmann_feature_history(database_path, 24)
    samples = [item["features"] for item in history if isinstance(item.get("features"), dict)]

    def current(feature_name: str, property_name: str) -> object:
        return raw_value(snapshot.features, feature_name, property_name)

    def numbers(feature_name: str, property_name: str) -> list[float]:
        values: list[float] = []
        for features in samples:
            value = raw_value(features, feature_name, property_name)
            if isinstance(value, (int, float)):
                values.append(float(value))
        return values

    def delta(feature_name: str, property_name: str) -> str:
        values = numbers(feature_name, property_name)
        return "nicht verfügbar" if len(values) < 2 else f"{max(0.0, values[-1] - values[0]):.1f}"

    def fmt(value: object, unit: str = "") -> str:
        if value is None:
            return "nicht verfügbar"
        if isinstance(value, float):
            return f"{value:.1f} {unit}".strip()
        return f"{value} {unit}".strip()

    active_samples = [bool(raw_value(features, "heating.compressors.0", "active")) for features in samples]
    active_ratio = sum(active_samples) / len(active_samples) if active_samples else None
    observed_hours = 24.0
    if len(history) >= 2:
        first = datetime.fromisoformat(str(history[0]["recorded_at"]).replace("Z", "+00:00"))
        last = datetime.fromisoformat(str(history[-1]["recorded_at"]).replace("Z", "+00:00"))
        observed_hours = max(0.0, (last - first).total_seconds() / 3600)
    supplied_energy = sum(
        float(raw_value(snapshot.features, feature_name, "currentDay") or 0)
        for feature_name in (
            "heating.power.consumption.summary.heating",
            "heating.power.consumption.summary.dhw",
        )
    )
    produced_energy = sum(
        float(raw_value(snapshot.features, feature_name, "currentDay") or 0)
        for feature_name in (
            "heating.heat.production.summary.heating",
            "heating.heat.production.summary.dhw",
        )
    )
    energy_ratio = produced_energy / supplied_energy if supplied_energy > 0 else None
    energy_ratio_display = (
        f"{energy_ratio:.2f}x"
        if energy_ratio is not None
        else f"n/a ({supplied_energy:.1f} kWh zugeführt)"
    )
    starts_24h = numbers("heating.compressors.0.statistics", "starts")
    hours_24h = numbers("heating.compressors.0.statistics", "hours")
    starts_delta = max(0.0, starts_24h[-1] - starts_24h[0]) if len(starts_24h) >= 2 else None
    hours_delta = max(0.0, hours_24h[-1] - hours_24h[0]) if len(hours_24h) >= 2 else None
    average_cycle = hours_delta * 60 / starts_delta if starts_delta and hours_delta is not None else None
    return_temperature = current("heating.sensors.temperature.return", "value")
    secondary_supply_temperature = current("heating.secondaryCircuit.sensors.temperature.supply", "value")
    temperature_spread = (
        float(secondary_supply_temperature) - float(return_temperature)
        if isinstance(secondary_supply_temperature, (int, float)) and isinstance(return_temperature, (int, float))
        else None
    )
    operating_mode = str(current("heating.secondaryCircuit.operation.state", "currentValue") or "nicht verfügbar")
    operating_mode = {"standby": "Bereitschaft", "heating": "Heizen", "dhw": "Warmwasser"}.get(operating_mode, operating_mode)
    kpis = [
        ("Verdichterstarts letzte 24h", delta("heating.compressors.0.statistics", "starts"), ""),
        ("Verdichterstarts gesamt", fmt(current("heating.compressors.0.statistics", "starts"), ""), ""),
        ("Verdichterlaufzeit letzte 24h", delta("heating.compressors.0.statistics", "hours"), "h"),
        ("Verdichterlaufzeit gesamt", fmt(current("heating.compressors.0.statistics", "hours"), "h"), ""),
        ("Außeneinheit aktiv letzte 24h", fmt(active_ratio * 100 if active_ratio is not None else None, "%"), ""),
        ("Außeneinheit aktiv im Beobachtungsfenster", fmt(active_ratio * observed_hours if active_ratio is not None else None, "h"), ""),
        ("Ø Verdichterlaufzeit je Start", fmt(average_cycle, "min"), ""),
        ("Außenlüfter 1 aktuell", fmt(current("heating.primaryCircuit.fans.0.current", "value"), "%"), ""),
        ("Außenlüfter 2 aktuell", fmt(current("heating.primaryCircuit.fans.1.current", "value"), "%"), ""),
        ("Außentemperatur", fmt(current("heating.sensors.temperature.outside", "value"), "°C"), ""),
        ("Heizkreis-Vorlauf", fmt(current("heating.circuits.0.sensors.temperature.supply", "value"), "°C"), ""),
        ("Anlagenrücklauf", fmt(current("heating.sensors.temperature.return", "value"), "°C"), ""),
        ("Pufferspeicher", fmt(current("heating.bufferCylinder.sensors.temperature.main", "value"), "°C"), ""),
        ("Warmwasserspeicher", fmt(current("heating.dhw.sensors.temperature.dhwCylinder", "value"), "°C"), ""),
        ("Interne Pumpe", fmt(current("heating.boiler.pumps.internal.current", "value"), "%"), ""),
        ("Heizstab für Heizen heute", fmt(current("heating.heatingRod.power.consumption.summary.heating", "currentDay"), "kWh"), ""),
        ("Heizstab für Warmwasser heute", fmt(current("heating.heatingRod.power.consumption.summary.dhw", "currentDay"), "kWh"), ""),
        ("Energie zugeführt heute", fmt(supplied_energy, "kWh"), ""),
        ("Energie erzeugt heute", fmt(produced_energy, "kWh"), ""),
        ("Energie-Ratio erzeugt / zugeführt heute", energy_ratio_display, ""),
        ("SPF Heizen", fmt(current("heating.spf.heating", "value"), ""), ""),
        ("SPF Warmwasser", fmt(current("heating.spf.dhw", "value"), ""), ""),
        ("SPF Gesamt", fmt(current("heating.spf.total", "value"), ""), ""),
        ("Sekundärkreis-Spreizung", fmt(temperature_spread, "°C"), ""),
        ("Elektrische Leistung aktuell", fmt(current("heating.power.consumption.current", "value"), "kW"), ""),
        ("Wärmeleistung aktuell", fmt(current("heating.heat.production.current", "value"), "kW"), ""),
        ("Betriebsmodus", operating_mode, ""),
        ("Abtauung", "aktiv" if bool(current("heating.outdoor.defrosting", "active")) else "inaktiv", ""),
        ("Verdichterstatus", f"aktiv ({current('heating.compressors.0', 'phase')})" if bool(current("heating.compressors.0", "active")) else f"bereit ({current('heating.compressors.0', 'phase')})", ""),
    ]
    st.markdown("### Wärmepumpen-Kennzahlen")
    st.caption("Aktuelle Werte und, soweit Snapshots vorhanden sind, berechnete Werte der letzten 24 Stunden.")
    for start in range(0, len(kpis), 3):
        columns = st.columns(3)
        for column, (label, value, _) in zip(columns, kpis[start:start + 3]):
            with column:
                st.metric(label, value)


def render_heat_pump_report(snapshot: object, history: list[dict[str, object]]) -> None:
    st.markdown('<div class="level-heading">Wärmepumpenbericht</div>', unsafe_allow_html=True)
    sections = report_sections(snapshot)
    latest_read = history[0]["recorded_at"] if history else "unbekannt"
    st.caption(f"{snapshot.model} | Geräte-ID {snapshot.device_id} | Read-only | Gelesen am: {latest_read}")

    render_heat_pump_kpis(snapshot, str(DATABASE_PATH))
    st.markdown("### Anlagenbild")
    st.caption("Schematische Live-Ansicht. Rot = Vorlauf, Blau = hydraulischer Rücklauf; Viessmann liefert hierfür keinen separaten Heizkreis-Sensor.")
    render_clear_heat_pump_schema(snapshot)
    st.markdown("### Viessmann-Komponentenbild")
    st.caption("Originalnahe Komponentenansicht mit den verfügbaren Viessmann-Livewerten.")
    render_viessmann_component_schema(snapshot)
    render_heating_curve(snapshot)

    status_columns = st.columns(4)
    with status_columns[0]:
        st.metric("Status", "Online" if snapshot.online else "Offline")
    with status_columns[1]:
        st.metric("Datenpunkte", sum(len(rows) for rows in sections.values()))
    with status_columns[2]:
        st.metric("Historische Snapshots", len(history))
    with status_columns[3]:
        st.metric("Bereiche", len(sections))

    for section_name, rows in sections.items():
        with st.expander(section_name, expanded=section_name in {"Status & Betrieb", "Temperaturen & Sensoren"}):
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Messwert": row["name"], "Wert": row["value"] or "-", "Einheit": row["unit"]}
                        for row in rows
                    ]
                ),
                hide_index=True,
                width="stretch",
                column_config={
                    "Messwert": st.column_config.TextColumn("Messwert", width="large"),
                    "Wert": st.column_config.TextColumn("Wert", width="medium"),
                    "Einheit": st.column_config.TextColumn("Einheit", width="small"),
                },
            )

    with st.container(border=True):
        st.markdown("### Historie")
        st.caption("Jeder erfolgreiche read-only Abruf wird als unveränderter Snapshot gespeichert.")
        if history:
            st.dataframe(
                pd.DataFrame(history),
                hide_index=True,
                width="stretch",
                column_config={
                    "recorded_at": "Zeitpunkt",
                    "device_id": "Gerät",
                    "model": "Modell",
                    "online": "Online",
                    "feature_count": "Datenpunkte",
                },
            )
        else:
            st.info("Noch keine historischen Snapshots vorhanden.")

    with st.expander("Technische Rohdaten"):
        st.json(snapshot.features)


def render_heat_pump_report_page(
    snapshot: Any,
    history: list[dict[str, object]],
    renderer: ReportRenderer,
) -> None:
    """Stable page boundary for the complete read-only heat-pump report."""
    renderer(snapshot, history)
