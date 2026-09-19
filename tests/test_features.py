from datetime import datetime, timezone

from src.feature_access import FeatureAccessor
from src.freshness import age_minutes, status
from src.viessmann_heatpump import HeatPumpSnapshot, system_map


def test_feature_accessor_reads_nested_value_properties() -> None:
    accessor = FeatureAccessor(
        {
            "data": [
                {
                    "feature": "heating.sensors.temperature.outside",
                    "properties": {
                        "value": {"value": 21.5, "unit": "celsius"},
                    },
                }
            ]
        }
    )

    assert accessor.value("heating.sensors.temperature.outside", "value") == 21.5
    assert accessor.value("missing", "value") is None


def test_freshness_status_uses_expected_interval() -> None:
    now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    timestamp = "2026-09-19T11:45:00+00:00"

    assert age_minutes(timestamp, now) == 15
    assert status(timestamp, 15, now) == "aktuell"
    assert status("2026-09-19T11:20:00+00:00", 15, now) == "veraltet"


def test_heat_pump_mapping_uses_floor_heating_circuit_supply() -> None:
    snapshot = HeatPumpSnapshot(
        device_id="test",
        model="Vitocal test",
        online=True,
        features={
            "data": [
                {
                    "feature": "heating.circuits.0.sensors.temperature.supply",
                    "properties": {"value": {"value": 26.7, "unit": "celsius"}},
                },
                {
                    "feature": "heating.secondaryCircuit.sensors.temperature.supply",
                    "properties": {"value": {"value": 54.5, "unit": "celsius"}},
                },
            ]
        },
    )

    heating_circuit = next(item for item in system_map(snapshot)["Heizkreis"] if item["name"] == "Heizkreis 1 Vorlauf")
    assert heating_circuit["value"] == "26.7 celsius"
