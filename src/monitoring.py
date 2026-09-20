from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.feature_access import FeatureAccessor
from src.freshness import age_minutes


@dataclass(frozen=True)
class SystemAlert:
    severity: str
    title: str
    detail: str


@dataclass(frozen=True)
class HeatPumpMetrics:
    compressor_active: bool
    compressor_phase: str
    starts_total: float | None
    starts_24h: float | None
    runtime_hours_total: float | None
    runtime_hours_24h: float | None
    average_cycle_minutes: float | None
    active_percent_24h: float | None
    current_power_kw: float | None
    current_heat_kw: float | None
    supplied_energy_today_kwh: float
    produced_energy_today_kwh: float
    energy_ratio_today: float | None
    daily_energy_cost: float | None
    floor_supply_celsius: float | None
    secondary_supply_celsius: float | None
    plant_return_celsius: float | None
    buffer_celsius: float | None
    dhw_celsius: float | None
    fan_1_percent: float | None
    fan_2_percent: float | None
    internal_pump_percent: float | None
    spf_total: float | None
    spf_heating: float | None
    spf_dhw: float | None
    operating_mode: str
    defrosting: bool
    heating_rod_ready: bool
    curve_slope: float | None
    curve_shift: float | None


def _number(accessor: FeatureAccessor, feature: str, property_name: str) -> float | None:
    value = accessor.value(feature, property_name)
    return float(value) if isinstance(value, (int, float)) else None


def _bool(accessor: FeatureAccessor, feature: str, property_name: str) -> bool:
    return bool(accessor.value(feature, property_name))


def _delta(history: list[dict[str, object]], feature: str, property_name: str) -> float | None:
    values: list[float] = []
    for item in history:
        features = item.get("features")
        if not isinstance(features, dict):
            continue
        value = _number(FeatureAccessor(features), feature, property_name)
        if value is not None:
            values.append(value)
    return max(0.0, values[-1] - values[0]) if len(values) >= 2 else None


def _active_percent(history: list[dict[str, object]]) -> float | None:
    states: list[bool] = []
    for item in history:
        features = item.get("features")
        if isinstance(features, dict):
            states.append(_bool(FeatureAccessor(features), "heating.compressors.0", "active"))
    return sum(states) / len(states) * 100 if states else None


def build_heat_pump_metrics(
    snapshot: Any,
    history: list[dict[str, object]],
    electricity_price: float = 0.30,
) -> HeatPumpMetrics:
    accessor = FeatureAccessor(snapshot.features)
    starts_total = _number(accessor, "heating.compressors.0.statistics", "starts")
    runtime_hours_total = _number(accessor, "heating.compressors.0.statistics", "hours")
    starts_24h = _delta(history, "heating.compressors.0.statistics", "starts")
    runtime_hours_24h = _delta(history, "heating.compressors.0.statistics", "hours")
    average_cycle_minutes = (
        runtime_hours_24h * 60 / starts_24h
        if starts_24h and runtime_hours_24h is not None
        else None
    )
    supplied_energy = sum(
        _number(accessor, feature, "currentDay") or 0.0
        for feature in (
            "heating.power.consumption.summary.heating",
            "heating.power.consumption.summary.dhw",
        )
    )
    produced_energy = sum(
        _number(accessor, feature, "currentDay") or 0.0
        for feature in (
            "heating.heat.production.summary.heating",
            "heating.heat.production.summary.dhw",
        )
    )
    mode = str(accessor.value("heating.secondaryCircuit.operation.state", "currentValue") or "unknown")
    return HeatPumpMetrics(
        compressor_active=_bool(accessor, "heating.compressors.0", "active"),
        compressor_phase=str(accessor.value("heating.compressors.0", "phase") or "unknown"),
        starts_total=starts_total,
        starts_24h=starts_24h,
        runtime_hours_total=runtime_hours_total,
        runtime_hours_24h=runtime_hours_24h,
        average_cycle_minutes=average_cycle_minutes,
        active_percent_24h=_active_percent(history),
        current_power_kw=_number(accessor, "heating.power.consumption.current", "value"),
        current_heat_kw=_number(accessor, "heating.heat.production.current", "value"),
        supplied_energy_today_kwh=supplied_energy,
        produced_energy_today_kwh=produced_energy,
        energy_ratio_today=produced_energy / supplied_energy if supplied_energy > 0 else None,
        daily_energy_cost=supplied_energy * electricity_price if supplied_energy > 0 else None,
        floor_supply_celsius=_number(accessor, "heating.circuits.0.sensors.temperature.supply", "value"),
        secondary_supply_celsius=_number(accessor, "heating.secondaryCircuit.sensors.temperature.supply", "value"),
        plant_return_celsius=_number(accessor, "heating.sensors.temperature.return", "value"),
        buffer_celsius=_number(accessor, "heating.bufferCylinder.sensors.temperature.main", "value"),
        dhw_celsius=_number(accessor, "heating.dhw.sensors.temperature.dhwCylinder", "value"),
        fan_1_percent=_number(accessor, "heating.primaryCircuit.fans.0.current", "value"),
        fan_2_percent=_number(accessor, "heating.primaryCircuit.fans.1.current", "value"),
        internal_pump_percent=_number(accessor, "heating.boiler.pumps.internal.current", "value"),
        spf_total=_number(accessor, "heating.spf.total", "value"),
        spf_heating=_number(accessor, "heating.spf.heating", "value"),
        spf_dhw=_number(accessor, "heating.spf.dhw", "value"),
        operating_mode=mode,
        defrosting=_bool(accessor, "heating.outdoor.defrosting", "active"),
        heating_rod_ready=_bool(accessor, "heating.heatingRod", "active"),
        curve_slope=_number(accessor, "heating.circuits.0.heating.curve", "slope"),
        curve_shift=_number(accessor, "heating.circuits.0.heating.curve", "shift"),
    )


def build_system_alerts(
    readings: list[dict[str, object]],
    timestamps: dict[str, str | None],
    metrics: HeatPumpMetrics | None,
    now: datetime | None = None,
) -> list[SystemAlert]:
    alerts: list[SystemAlert] = []
    homematic_age = age_minutes(timestamps.get("homematic"), now)
    viessmann_age = age_minutes(timestamps.get("viessmann"), now)
    if homematic_age is None or homematic_age > 30:
        alerts.append(SystemAlert("warning", "Homematic-Daten veraltet", "Es gibt seit über 30 Minuten keinen erfolgreichen Homematic-Snapshot."))
    if viessmann_age is None or viessmann_age > 60:
        alerts.append(SystemAlert("warning", "Viessmann-Daten veraltet", "Es gibt seit über 60 Minuten keinen erfolgreichen Viessmann-Snapshot."))

    below_target = [
        str(reading["room_name"])
        for reading in readings
        if float(reading["target_temperature"]) - float(reading["current_temperature"]) > 0.5
        and float(reading["valve_position"]) > 0
    ]
    if below_target:
        alerts.append(SystemAlert("warning", "Räume unter Zieltemperatur", ", ".join(below_target[:4])))
    if metrics is not None:
        if metrics.defrosting:
            alerts.append(SystemAlert("info", "Abtauung aktiv", "Die Außeneinheit befindet sich im Abtauvorgang."))
        if metrics.compressor_active and (metrics.current_heat_kw or 0) <= 0:
            alerts.append(SystemAlert("warning", "Verdichter ohne Wärmeleistung", "Der Verdichter ist aktiv, aber aktuell wird keine Wärmeleistung gemeldet."))
        if metrics.supplied_energy_today_kwh <= 0 and metrics.produced_energy_today_kwh > 0:
            alerts.append(
                SystemAlert(
                    "info",
                    "Stromverbrauch nicht gemeldet",
                    f"Viessmann meldet heute {metrics.supplied_energy_today_kwh:.1f} kWh Stromverbrauch, obwohl {metrics.produced_energy_today_kwh:.1f} kWh Wärme erzeugt wurden. Verbrauchszähler und Viessmann-Datenversorgung prüfen.",
                )
            )
    return alerts