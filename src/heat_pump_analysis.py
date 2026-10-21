"""Pure analysis functions for heat-pump performance (no Streamlit dependency).

Operates on the archived Viessmann feature history produced by
``src.database.get_viessmann_feature_history`` (list of
``{"recorded_at": iso, "features": {...}}`` dicts, ascending by time).

Sampling caveat: snapshots are taken every ~30 minutes. Compressor start
counts and runtimes derived from the monotonic statistics counters are exact;
on/off *timestamps* derived from the ``active`` flag are coarse (±interval).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from typing import Any

from src.feature_access import FeatureAccessor

CURVE_MIN_SUPPLY = 10.0
CURVE_MAX_SUPPLY = 40.0
DEFAULT_ROOM_TARGET = 20.0
SHORT_CYCLE_MINUTES = 10.0
WARN_CYCLE_MINUTES = 20.0
RESIDUAL_WARN_K = 2.0
FLOOR_SUPPLY_AT_ZERO_WARN = 35.0
RADIATOR_SUPPLY_AT_ZERO_WARN = 45.0
ROD_SHARE_WARN_PCT = 5.0
ROD_SHARE_CRITICAL_PCT = 15.0
STARTS_PER_DAY_WARN = 12.0
STARTS_PER_DAY_CRITICAL = 24.0


@dataclass(frozen=True)
class Sample:
    recorded_at: datetime
    outside_celsius: float | None
    supply_celsius: float | None
    supply_target_celsius: float | None
    return_celsius: float | None
    compressor_active: bool
    starts_total: float | None
    runtime_hours_total: float | None


@dataclass(frozen=True)
class CurveFit:
    configured_slope: float | None
    configured_shift: float | None
    empirical_slope: float | None
    empirical_intercept: float | None
    sample_count: int
    median_residual_k: float | None
    median_active_deviation_k: float | None
    overshoot_share: float | None
    verdict: str
    verdict_detail: str


@dataclass(frozen=True)
class CycleEvent:
    started_at: datetime
    ended_at: datetime | None
    duration_minutes: float | None
    deviation_at_start_k: float | None
    deviation_at_end_k: float | None


@dataclass(frozen=True)
class CycleStats:
    window_hours: float
    starts: float | None
    runtime_hours: float | None
    starts_per_day: float | None
    avg_cycle_minutes: float | None
    duty_cycle_pct: float | None
    observed_cycles: tuple[CycleEvent, ...]


@dataclass(frozen=True)
class HysteresisEstimate:
    switch_on_k: float | None
    switch_off_k: float | None
    event_count: int


@dataclass(frozen=True)
class DailyCycling:
    day: str
    starts: float | None
    runtime_hours: float | None
    avg_cycle_minutes: float | None
    avg_outside_celsius: float | None
    duty_cycle_pct: float | None


@dataclass(frozen=True)
class Finding:
    severity: str  # "critical" | "warning" | "info" | "ok"
    title: str
    detail: str
    recommendation: str


@dataclass(frozen=True)
class PerformanceReport:
    curve: CurveFit
    hysteresis: HysteresisEstimate
    cycling: CycleStats
    daily: tuple[DailyCycling, ...]
    rod_share_pct: float | None
    score: int
    score_label: str
    findings: tuple[Finding, ...] = field(default_factory=tuple)


def curve_target_celsius(
    outside_celsius: float,
    slope: float,
    shift: float,
    room_target: float = DEFAULT_ROOM_TARGET,
) -> float:
    """Approximated Viessmann curve target (same formula as the dashboard curve renderer)."""
    target = room_target + slope * (room_target - outside_celsius) + shift
    return max(CURVE_MIN_SUPPLY, min(CURVE_MAX_SUPPLY, target))


def _number(accessor: FeatureAccessor, feature: str, property_name: str) -> float | None:
    value = accessor.value(feature, property_name)
    return float(value) if isinstance(value, (int, float)) else None


def extract_samples(history: list[dict[str, Any]], circuit: int = 0) -> list[Sample]:
    samples: list[Sample] = []
    for item in history:
        features = item.get("features")
        if not isinstance(features, dict):
            continue
        try:
            recorded_at = datetime.fromisoformat(str(item["recorded_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        accessor = FeatureAccessor(features)
        active_value = accessor.value("heating.compressors.0", "active")
        samples.append(
            Sample(
                recorded_at=recorded_at,
                outside_celsius=_number(accessor, "heating.sensors.temperature.outside", "value"),
                supply_celsius=_number(accessor, f"heating.circuits.{circuit}.sensors.temperature.supply", "value"),
                supply_target_celsius=_number(accessor, f"heating.circuits.{circuit}.temperature", "value"),
                return_celsius=_number(accessor, "heating.sensors.temperature.return", "value"),
                compressor_active=bool(active_value),
                starts_total=_number(accessor, "heating.compressors.0.statistics", "starts"),
                runtime_hours_total=_number(accessor, "heating.compressors.0.statistics", "hours"),
            )
        )
    return samples


def _linear_regression(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Least-squares fit, returns (slope, intercept) or None if degenerate."""
    if len(points) < 3:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return None
    cov_xy = sum((x - mean_x) * (y - mean_y) for x, y in points)
    slope = cov_xy / var_x
    return slope, mean_y - slope * mean_x


def _median(values: list[float]) -> float | None:
    return median(values) if values else None


def fit_heating_curve(
    history: list[dict[str, Any]],
    circuit: int = 0,
    room_target: float = DEFAULT_ROOM_TARGET,
) -> CurveFit:
    samples = extract_samples(history, circuit)
    configured_slope: float | None = None
    configured_shift: float | None = None
    if samples:
        # Use the newest sample: current configuration.
        newest_features = None
        for item in reversed(history):
            features = item.get("features")
            if isinstance(features, dict):
                newest_features = features
                break
        if newest_features is not None:
            accessor = FeatureAccessor(newest_features)
            configured_slope = _number(accessor, f"heating.circuits.{circuit}.heating.curve", "slope")
            configured_shift = _number(accessor, f"heating.circuits.{circuit}.heating.curve", "shift")

    points = [
        (sample.outside_celsius, sample.supply_celsius)
        for sample in samples
        if sample.outside_celsius is not None and sample.supply_celsius is not None
    ]
    regression = _linear_regression(points)
    # Regression gives supply = intercept + slope * outside (negative slope).
    # Report in Heizkurve convention: positive slope, intercept = supply at 0 °C.
    empirical_slope = -regression[0] if regression else None
    empirical_intercept = regression[1] if regression else None

    residuals: list[float] = []
    if configured_slope is not None and configured_shift is not None:
        for outside, supply in points:
            target = curve_target_celsius(outside, configured_slope, configured_shift, room_target)
            residuals.append(supply - target)
    median_residual = _median(residuals)
    overshoot_share = (
        sum(1 for residual in residuals if residual > RESIDUAL_WARN_K) / len(residuals)
        if residuals
        else None
    )

    # Model-free signal: deviation of supply from the controller's own setpoint
    # while the compressor is running. Preferred over the linear curve
    # approximation, which can diverge from Viessmann's real curve shape.
    active_deviations = [
        sample.supply_celsius - sample.supply_target_celsius
        for sample in samples
        if sample.supply_celsius is not None
        and sample.supply_target_celsius is not None
        and sample.compressor_active
    ]
    median_active_deviation = _median(active_deviations)

    if len(active_deviations) >= 10:
        basis, basis_label = median_active_deviation, "Regler-Soll (bei laufendem Verdichter)"
    else:
        basis, basis_label = median_residual, "Kurven-Soll (linearer Näherung)"

    if len(points) < 10 or basis is None:
        verdict, detail = "keine daten", "Zu wenige Messpunkte für eine Heizkurven-Bewertung."
    elif basis > RESIDUAL_WARN_K:
        verdict = "zu hoch"
        detail = (
            f"Der Ist-Vorlauf liegt im Median {basis:.1f} K über dem {basis_label}. "
            "Das deutet auf eine zu hoch eingestellte Heizkurve hin."
        )
    elif basis < -RESIDUAL_WARN_K:
        verdict = "zu niedrig"
        detail = (
            f"Der Ist-Vorlauf liegt im Median {abs(basis):.1f} K unter dem {basis_label}. "
            "Komfort oder Regelung prüfen."
        )
    else:
        verdict = "optimal"
        detail = f"Ist-Vorlauf folgt dem {basis_label} (Median-Abweichung {basis:+.1f} K)."

    return CurveFit(
        configured_slope=configured_slope,
        configured_shift=configured_shift,
        empirical_slope=empirical_slope,
        empirical_intercept=empirical_intercept,
        sample_count=len(points),
        median_residual_k=median_residual,
        median_active_deviation_k=median_active_deviation,
        overshoot_share=overshoot_share,
        verdict=verdict,
        verdict_detail=detail,
    )


def _counter_delta(samples: list[Sample], attribute: str) -> float | None:
    values = [getattr(sample, attribute) for sample in samples]
    values = [value for value in values if value is not None]
    if len(values) < 2:
        return None
    return max(0.0, values[-1] - values[0])


def _detect_cycles(samples: list[Sample]) -> tuple[CycleEvent, ...]:
    cycles: list[CycleEvent] = []
    active_start: Sample | None = None
    last_active: Sample | None = None
    for sample in samples:
        if sample.compressor_active and active_start is None:
            active_start = sample
        if sample.compressor_active:
            last_active = sample
        elif active_start is not None:
            deviation_start = _deviation(active_start)
            deviation_end = _deviation(last_active) if last_active else None
            duration = (sample.recorded_at - active_start.recorded_at).total_seconds() / 60
            cycles.append(
                CycleEvent(
                    started_at=active_start.recorded_at,
                    ended_at=sample.recorded_at,
                    duration_minutes=duration,
                    deviation_at_start_k=deviation_start,
                    deviation_at_end_k=deviation_end,
                )
            )
            active_start = None
            last_active = None
    if active_start is not None:
        cycles.append(
            CycleEvent(
                started_at=active_start.recorded_at,
                ended_at=None,
                duration_minutes=None,
                deviation_at_start_k=_deviation(active_start),
                deviation_at_end_k=_deviation(last_active) if last_active else None,
            )
        )
    return tuple(cycles)


def _deviation(sample: Sample | None) -> float | None:
    if sample is None or sample.supply_celsius is None or sample.supply_target_celsius is None:
        return None
    return sample.supply_celsius - sample.supply_target_celsius


def analyze_cycling(history: list[dict[str, Any]], circuit: int = 0) -> CycleStats:
    samples = extract_samples(history, circuit)
    window_hours = 0.0
    if len(samples) >= 2:
        window_hours = (samples[-1].recorded_at - samples[0].recorded_at).total_seconds() / 3600

    starts = _counter_delta(samples, "starts_total")
    runtime_hours = _counter_delta(samples, "runtime_hours_total")
    starts_per_day = starts * 24 / window_hours if starts is not None and window_hours > 0 else None
    avg_cycle_minutes = (
        runtime_hours * 60 / starts if starts and runtime_hours is not None and starts > 0 else None
    )
    active_flags = [sample.compressor_active for sample in samples]
    duty_cycle_pct = (sum(active_flags) / len(active_flags) * 100) if active_flags else None
    cycles = _detect_cycles(samples)

    return CycleStats(
        window_hours=window_hours,
        starts=starts,
        runtime_hours=runtime_hours,
        starts_per_day=starts_per_day,
        avg_cycle_minutes=avg_cycle_minutes,
        duty_cycle_pct=duty_cycle_pct,
        observed_cycles=cycles,
    )


def estimate_hysteresis(history: list[dict[str, Any]], circuit: int = 0) -> HysteresisEstimate:
    """Estimate effective switch hysteresis from observed start/stop deviations.

    The configured heating hysteresis is not exposed by the API on all units, so
    this derives it empirically: deviation of supply temperature from setpoint at
    the moment the compressor switches on/off. Precision is limited by the
    snapshot interval (~30 min).
    """
    samples = extract_samples(history, circuit)
    cycles = _detect_cycles(samples)
    on_deviations = [c.deviation_at_start_k for c in cycles if c.deviation_at_start_k is not None]
    off_deviations = [c.deviation_at_end_k for c in cycles if c.deviation_at_end_k is not None]
    return HysteresisEstimate(
        switch_on_k=_median(on_deviations),
        switch_off_k=_median(off_deviations),
        event_count=len(on_deviations),
    )


def daily_cycling(history: list[dict[str, Any]], circuit: int = 0) -> tuple[DailyCycling, ...]:
    samples = extract_samples(history, circuit)
    by_day: dict[str, list[Sample]] = {}
    for sample in samples:
        by_day.setdefault(sample.recorded_at.date().isoformat(), []).append(sample)

    result: list[DailyCycling] = []
    for day in sorted(by_day):
        day_samples = by_day[day]
        starts = _counter_delta(day_samples, "starts_total")
        runtime = _counter_delta(day_samples, "runtime_hours_total")
        avg_cycle = runtime * 60 / starts if starts and runtime is not None and starts > 0 else None
        outside_values = [s.outside_celsius for s in day_samples if s.outside_celsius is not None]
        duty = sum(s.compressor_active for s in day_samples) / len(day_samples) * 100
        result.append(
            DailyCycling(
                day=day,
                starts=starts,
                runtime_hours=runtime,
                avg_cycle_minutes=avg_cycle,
                avg_outside_celsius=(sum(outside_values) / len(outside_values)) if outside_values else None,
                duty_cycle_pct=duty,
            )
        )
    return tuple(result)


def heating_rod_share_pct(history: list[dict[str, Any]]) -> float | None:
    """Share of heating-rod energy in today's produced heat (from daily counters)."""
    for item in reversed(history):
        features = item.get("features")
        if not isinstance(features, dict):
            continue
        accessor = FeatureAccessor(features)
        rod = sum(
            _number(accessor, feature, "currentDay") or 0.0
            for feature in (
                "heating.heatingRod.power.consumption.summary.heating",
                "heating.heatingRod.power.consumption.summary.dhw",
            )
        )
        produced = sum(
            _number(accessor, feature, "currentDay") or 0.0
            for feature in (
                "heating.heat.production.summary.heating",
                "heating.heat.production.summary.dhw",
            )
        )
        if produced > 0:
            return rod / produced * 100
        return None
    return None


def analyze_performance(
    history: list[dict[str, Any]],
    *,
    circuit: int = 0,
    floor_heating: bool = True,
    room_target: float = DEFAULT_ROOM_TARGET,
) -> PerformanceReport:
    curve = fit_heating_curve(history, circuit, room_target)
    cycling = analyze_cycling(history, circuit)
    hysteresis = estimate_hysteresis(history, circuit)
    daily = daily_cycling(history, circuit)
    rod_share = heating_rod_share_pct(history)

    findings: list[Finding] = []

    # Cycling / longevity
    if cycling.avg_cycle_minutes is None:
        if cycling.starts is not None and cycling.starts == 0:
            findings.append(Finding("info", "Keine Verdichterstarts im Zeitraum", "Der Verdichter lief im gewählten Zeitraum nicht.", "Bei Heizbetrieb prüfen, ob der Zeitraum repräsentativ ist."))
        else:
            findings.append(Finding("info", "Taktung nicht bewertbar", "Zu wenige Daten im gewählten Zeitraum.", "Zeitraum vergrößern."))
    elif cycling.avg_cycle_minutes < SHORT_CYCLE_MINUTES:
        findings.append(Finding("critical", "Starkes Takten", f"Ø Verdichterlaufzeit je Start beträgt nur {cycling.avg_cycle_minutes:.0f} min.", "Heizkurve senken, Hysterese vergrößern oder Pufferspeicher-Volumen prüfen. Starkes Takten verkürzt die Verdichter-Lebensdauer deutlich."))
    elif cycling.avg_cycle_minutes < WARN_CYCLE_MINUTES:
        findings.append(Finding("warning", "Erhöhtes Takten", f"Ø Verdichterlaufzeit je Start beträgt {cycling.avg_cycle_minutes:.0f} min.", "Zyklen über ~20 min sind schonender. Heizkurve leicht senken oder Hysterese vergrößern."))
    else:
        findings.append(Finding("ok", "Schonende Taktung", f"Ø Verdichterlaufzeit je Start beträgt {cycling.avg_cycle_minutes:.0f} min.", "Kein Handlungsbedarf."))

    if cycling.starts_per_day is not None:
        if cycling.starts_per_day > STARTS_PER_DAY_CRITICAL:
            findings.append(Finding("critical", "Sehr viele Verdichterstarts", f"{cycling.starts_per_day:.0f} Starts pro Tag.", "Mehr als ~24 Starts/Tag belasten den Verdichter. Regelparameter prüfen."))
        elif cycling.starts_per_day > STARTS_PER_DAY_WARN:
            findings.append(Finding("warning", "Viele Verdichterstarts", f"{cycling.starts_per_day:.0f} Starts pro Tag.", "Weniger als ~12 Starts/Tag sind erstrebenswert."))

    # Heating curve
    if curve.verdict == "zu hoch":
        findings.append(Finding("warning", "Heizkurve zu hoch", curve.verdict_detail, "Neigung oder Niveau schrittweise um 0,1 bzw. 1 K senken und Raumtemperaturen beobachten."))
    elif curve.verdict == "zu niedrig":
        findings.append(Finding("warning", "Heizkurve zu niedrig", curve.verdict_detail, "Neigung oder Niveau leicht erhöhen, falls Räume nicht warm werden."))
    elif curve.verdict == "optimal":
        findings.append(Finding("ok", "Heizkurve passt", curve.verdict_detail, "Kein Handlungsbedarf."))

    supply_limit = FLOOR_SUPPLY_AT_ZERO_WARN if floor_heating else RADIATOR_SUPPLY_AT_ZERO_WARN
    if curve.empirical_intercept is not None and curve.empirical_intercept > supply_limit:
        kind = "Fußbodenheizung" if floor_heating else "Heizkörper"
        findings.append(Finding("warning", "Hohe Vorlauftemperatur", f"Geschätzte Vorlauftemperatur bei 0 °C außen: {curve.empirical_intercept:.0f} °C ({kind}-Richtwert {supply_limit:.0f} °C).", "Niedrigere Vorlauftemperaturen erhöhen die Jahresarbeitszahl und schonen die Anlage."))

    # Hysteresis
    if hysteresis.switch_on_k is not None and abs(hysteresis.switch_on_k) < 2.0:
        findings.append(Finding("info", "Enge Einschalthysterese", f"Geschätzte Einschaltschwelle: {hysteresis.switch_on_k:+.1f} K unter Soll.", "Eine größere Hysterese (z. B. 3–5 K) verlängert die Verdichterzyklen."))

    # Heating rod
    if rod_share is not None and rod_share > ROD_SHARE_CRITICAL_PCT:
        findings.append(Finding("critical", "Heizstab-Anteil sehr hoch", f"{rod_share:.0f} % der heute erzeugten Wärme stammt vom Heizstab.", "Heizstabbetrieb ist ineffizient. Freigabegrenzen und Wärmepumpen-Leistung prüfen."))
    elif rod_share is not None and rod_share > ROD_SHARE_WARN_PCT:
        findings.append(Finding("warning", "Heizstab-Anteil erhöht", f"{rod_share:.0f} % der heute erzeugten Wärme stammt vom Heizstab.", "Anteil beobachten; dauerhaft >5 % deutet auf Unterdimensionierung oder falsche Einstellungen hin."))

    severity_penalty = {"critical": 30, "warning": 15, "info": 5, "ok": 0}
    score = max(0, 100 - sum(severity_penalty.get(f.severity, 0) for f in findings))
    if score >= 85:
        label = "optimal"
    elif score >= 65:
        label = "gut"
    elif score >= 40:
        label = "verbesserbar"
    else:
        label = "kritisch"

    return PerformanceReport(
        curve=curve,
        hysteresis=hysteresis,
        cycling=cycling,
        daily=daily,
        rod_share_pct=rod_share,
        score=score,
        score_label=label,
        findings=tuple(findings),
    )
