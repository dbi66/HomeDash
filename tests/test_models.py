from datetime import datetime, timezone

from src.models import DataQuality, FeatureValue, SensorReading, SnapshotContract


def test_feature_value_models_raw_payloads() -> None:
    value = FeatureValue.from_raw(
        {
            "feature": "heating.compressors.0",
            "properties": {
                "phase": {"value": {"value": "heating"}},
                "active": {"value": {"value": True}},
                "current": {"value": {"value": 42.0}, "unit": "%"},
            },
        },
        "phase",
    )

    assert value.feature == "heating.compressors.0"
    assert value.property == "phase"
    assert value.value == "heating"
    assert value.unit == ""
    assert value["feature"] == "heating.compressors.0"
    assert value["value"] == "heating"


def test_sensor_contract_preserves_source_timestamp_and_quality() -> None:
    recorded_at = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    source_timestamp = datetime(2026, 9, 20, 11, 59, tzinfo=timezone.utc)

    reading = SensorReading(
        sensor_id="living-room.temperature",
        value=22.4,
        unit="C",
        recorded_at=recorded_at,
        source_timestamp=source_timestamp,
        quality=DataQuality.DEGRADED,
        is_stale=True,
    )

    assert reading.source_timestamp == source_timestamp
    assert reading.quality == DataQuality.DEGRADED
    assert reading.is_stale is True


def test_snapshot_contract_defaults_to_good_quality() -> None:
    snapshot = SnapshotContract(
        provider="homematic",
        recorded_at=datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc),
    )

    assert snapshot.quality == DataQuality.GOOD
    assert snapshot.source_timestamp is None
    assert snapshot.is_stale is False
