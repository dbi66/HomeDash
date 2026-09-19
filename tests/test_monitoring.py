from datetime import datetime, timezone

from src.monitoring import build_heat_pump_metrics, build_system_alerts
from src.viessmann_heatpump import HeatPumpSnapshot


def make_snapshot() -> HeatPumpSnapshot:
    def number_feature(name: str, property_name: str, value: float) -> dict[str, object]:
        return {
            "feature": name,
            "properties": {property_name: {"value": {"value": value, "unit": ""}}},
        }

    return HeatPumpSnapshot(
        device_id="test",
        model="Vitocal test",
        online=True,
        features={
            "data": [
                {"feature": "heating.compressors.0", "properties": {"active": {"value": False}, "phase": {"value": "ready"}}},
                number_feature("heating.compressors.0.statistics", "starts", 12),
                number_feature("heating.compressors.0.statistics", "hours", 20),
                number_feature("heating.circuits.0.sensors.temperature.supply", "value", 26.7),
                number_feature("heating.power.consumption.summary.heating", "currentDay", 2),
                number_feature("heating.heat.production.summary.heating", "currentDay", 8),
            ]
        },
    )


def test_monitoring_metrics_calculate_daily_energy_and_cycles() -> None:
    snapshot = make_snapshot()
    history = [
        {"recorded_at": "2026-09-19T10:00:00+00:00", "features": {"data": [{"feature": "heating.compressors.0.statistics", "properties": {"starts": {"value": {"value": 10}}, "hours": {"value": {"value": 18}}}}]}},
        {"recorded_at": "2026-09-19T11:00:00+00:00", "features": {"data": [{"feature": "heating.compressors.0.statistics", "properties": {"starts": {"value": {"value": 12}}, "hours": {"value": {"value": 20}}}}]}},
    ]

    metrics = build_heat_pump_metrics(snapshot, history)

    assert metrics.starts_24h == 2
    assert metrics.runtime_hours_24h == 2
    assert metrics.average_cycle_minutes == 60
    assert metrics.energy_ratio_today == 4
    assert metrics.floor_supply_celsius == 26.7


def test_monitoring_alerts_flag_stale_data_and_rooms_below_target() -> None:
    readings = [{"room_name": "Bad", "current_temperature": 19.0, "target_temperature": 21.0, "valve_position": 50}]
    alerts = build_system_alerts(
        readings,
        {"homematic": "2026-09-19T10:00:00+00:00", "viessmann": "2026-09-19T09:59:00+00:00"},
        None,
        now=datetime(2026, 9, 19, 11, 0, tzinfo=timezone.utc),
    )

    assert {alert.title for alert in alerts} == {"Homematic-Daten veraltet", "Viessmann-Daten veraltet", "Räume unter Zieltemperatur"}
