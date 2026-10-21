from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.heat_pump_analysis import (
    analyze_cycling,
    analyze_performance,
    curve_target_celsius,
    daily_cycling,
    estimate_hysteresis,
    extract_samples,
    fit_heating_curve,
    heating_rod_share_pct,
)

BASE_TIME = datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc)


def make_features(
    *,
    outside=None,
    supply=None,
    target=None,
    return_t=None,
    active=None,
    starts=None,
    hours=None,
    slope=None,
    shift=None,
    rod_heating=None,
    rod_dhw=None,
    produced_heating=None,
    produced_dhw=None,
) -> dict:
    data = []

    def add(feature: str, properties: dict) -> None:
        data.append({"feature": feature, "properties": properties})

    if outside is not None:
        add("heating.sensors.temperature.outside", {"value": {"value": outside}})
    if supply is not None:
        add("heating.circuits.0.sensors.temperature.supply", {"value": {"value": supply}})
    if target is not None:
        add("heating.circuits.0.temperature", {"value": {"value": target}})
    if return_t is not None:
        add("heating.sensors.temperature.return", {"value": {"value": return_t}})
    if active is not None:
        add("heating.compressors.0", {"active": {"value": active}})
    if starts is not None or hours is not None:
        props = {}
        if starts is not None:
            props["starts"] = {"value": starts}
        if hours is not None:
            props["hours"] = {"value": hours}
        add("heating.compressors.0.statistics", props)
    if slope is not None or shift is not None:
        props = {}
        if slope is not None:
            props["slope"] = {"value": slope}
        if shift is not None:
            props["shift"] = {"value": shift}
        add("heating.circuits.0.heating.curve", props)
    if rod_heating is not None:
        add("heating.heatingRod.power.consumption.summary.heating", {"currentDay": {"value": rod_heating}})
    if rod_dhw is not None:
        add("heating.heatingRod.power.consumption.summary.dhw", {"currentDay": {"value": rod_dhw}})
    if produced_heating is not None:
        add("heating.heat.production.summary.heating", {"currentDay": {"value": produced_heating}})
    if produced_dhw is not None:
        add("heating.heat.production.summary.dhw", {"currentDay": {"value": produced_dhw}})
    return {"data": data}


def item(minutes: float, **kwargs) -> dict:
    return {
        "recorded_at": (BASE_TIME + timedelta(minutes=minutes)).isoformat(),
        "features": make_features(**kwargs),
    }


def test_curve_target_matches_dashboard_formula() -> None:
    assert curve_target_celsius(0, 0.4, 0) == 28.0
    assert curve_target_celsius(-30, 0.8, 5) == 40.0  # clamped
    assert curve_target_celsius(30, 0.4, 0) == 16.0
    assert curve_target_celsius(50, 0.4, 0) == 10.0  # clamped


def test_extract_samples_parses_features() -> None:
    history = [item(0, outside=5.0, supply=30.0, target=31.0, active=True, starts=100, hours=50.0)]
    samples = extract_samples(history)
    assert len(samples) == 1
    sample = samples[0]
    assert sample.outside_celsius == 5.0
    assert sample.supply_celsius == 30.0
    assert sample.supply_target_celsius == 31.0
    assert sample.compressor_active is True
    assert sample.starts_total == 100.0


def test_fit_heating_curve_matches_configuration() -> None:
    # Actual supply follows the configured curve exactly: slope 0.4, shift 0.
    history = []
    for index, outside in enumerate([-10.0, -5.0, 0.0, 5.0, 10.0] * 4):
        supply = curve_target_celsius(outside, 0.4, 0.0)
        history.append(item(index * 30, outside=outside, supply=supply, slope=0.4, shift=0.0))
    fit = fit_heating_curve(history)
    assert fit.configured_slope == 0.4
    assert fit.empirical_slope is not None and abs(fit.empirical_slope - 0.4) < 0.01
    assert fit.empirical_intercept is not None and abs(fit.empirical_intercept - 28.0) < 0.5
    assert fit.median_residual_k is not None and abs(fit.median_residual_k) < 0.01
    assert fit.verdict == "optimal"


def test_fit_heating_curve_detects_actual_above_configured() -> None:
    # Unit delivers ~4 K above the configured curve.
    history = []
    for index, outside in enumerate([-10.0, -5.0, 0.0, 5.0, 10.0] * 4):
        supply = curve_target_celsius(outside, 0.4, 0.0) + 4.0
        history.append(item(index * 30, outside=outside, supply=supply, slope=0.4, shift=0.0))
    fit = fit_heating_curve(history)
    assert fit.verdict == "zu hoch"
    assert fit.median_residual_k is not None and fit.median_residual_k > 3.5
    assert fit.overshoot_share == 1.0


def test_fit_heating_curve_without_data() -> None:
    fit = fit_heating_curve([])
    assert fit.verdict == "keine daten"
    assert fit.sample_count == 0


def test_analyze_cycling_uses_counter_deltas() -> None:
    # 24 h window, 30-min sampling: +4 starts, +2 h runtime -> 30 min/cycle.
    history = []
    for index in range(48):
        active = index % 4 in (1, 2)  # 50 % duty
        history.append(
            item(
                index * 30,
                outside=3.0,
                supply=30.0,
                target=30.0,
                active=active,
                starts=100 + 4 * index / 47,
                hours=50.0 + 2.0 * index / 47,
            )
        )
    stats = analyze_cycling(history)
    assert stats.starts is not None and abs(stats.starts - 4.0) < 0.01
    assert stats.runtime_hours is not None and abs(stats.runtime_hours - 2.0) < 0.01
    assert stats.avg_cycle_minutes is not None and abs(stats.avg_cycle_minutes - 30.0) < 0.5
    assert stats.duty_cycle_pct == 50.0
    assert stats.starts_per_day is not None and 3.5 < stats.starts_per_day < 4.5


def test_estimate_hysteresis_from_switch_points() -> None:
    # Two cycles: compressor on at supply 2 K below target, off at 2 K above.
    pattern = [
        (0, False, 30.0),
        (30, False, 29.0),
        (60, True, 28.0),   # start, deviation -2
        (90, True, 31.0),
        (120, False, 32.0),  # stop, deviation +2 (last active = 31.0 -> +1)
        (150, False, 30.0),
        (180, True, 28.0),
        (210, True, 31.0),
        (240, False, 32.0),
    ]
    history = [item(minutes, active=active, supply=supply, target=30.0, starts=0, hours=0.0) for minutes, active, supply in pattern]
    estimate = estimate_hysteresis(history)
    assert estimate.event_count == 2
    assert estimate.switch_on_k == -2.0
    assert estimate.switch_off_k == 1.0


def test_daily_cycling_groups_by_day() -> None:
    history = []
    for day in range(3):
        for slot in range(4):
            minutes = day * 24 * 60 + slot * 30
            history.append(
                item(
                    minutes,
                    outside=5.0 + day,
                    active=slot % 2 == 0,
                    starts=day * 10 + slot * 2,
                    hours=day * 5.0 + slot * 0.5,
                )
            )
    daily = daily_cycling(history)
    assert len(daily) == 3
    assert daily[1].starts == 6.0
    assert daily[1].avg_outside_celsius == 6.0
    assert daily[1].duty_cycle_pct == 50.0


def test_heating_rod_share_uses_latest_day_counters() -> None:
    history = [
        item(0, rod_heating=0.0, rod_dhw=0.0, produced_heating=5.0, produced_dhw=2.0),
        item(30, rod_heating=2.0, rod_dhw=1.0, produced_heating=15.0, produced_dhw=5.0),
    ]
    assert heating_rod_share_pct(history) == 15.0


def test_analyze_performance_flags_short_cycling() -> None:
    # 24 h, +24 starts, +2.4 h runtime -> 6 min/cycle: critical.
    history = []
    for index in range(49):
        fraction = index / 48
        history.append(
            item(
                index * 30,
                outside=8.0,
                supply=28.0,
                target=30.0,
                active=index % 2 == 0,
                starts=200 + 24 * fraction,
                hours=80.0 + 2.4 * fraction,
                slope=0.4,
                shift=0.0,
            )
        )
    report = analyze_performance(history)
    titles = [finding.title for finding in report.findings]
    assert "Starkes Takten" in titles
    assert report.cycling.avg_cycle_minutes is not None and report.cycling.avg_cycle_minutes < 10
    assert report.score <= 60
    assert report.score_label in ("verbesserbar", "kritisch")


def test_analyze_performance_healthy_system_scores_high() -> None:
    # Well-behaved: 4 starts/day, 30 min cycles, supply follows curve.
    history = []
    for index in range(49):
        outside = 2.0 + (index % 7) - 3
        supply = curve_target_celsius(outside, 0.4, 0.0)
        fraction = index / 48
        history.append(
            item(
                index * 30,
                outside=outside,
                supply=supply,
                target=supply,
                active=index % 8 in (1, 2, 3, 4),
                starts=100 + 4 * fraction,
                hours=50.0 + 2.0 * fraction,
                slope=0.4,
                shift=0.0,
                rod_heating=0.0,
                rod_dhw=0.0,
                produced_heating=10.0,
                produced_dhw=3.0,
            )
        )
    report = analyze_performance(history)
    assert report.score >= 85
    assert report.score_label == "optimal"
    assert any(finding.title == "Heizkurve passt" for finding in report.findings)


def test_analyze_performance_handles_empty_history() -> None:
    report = analyze_performance([])
    assert report.curve.verdict == "keine daten"
    assert report.cycling.starts is None
    assert 0 <= report.score <= 100
