from src.models import FeatureValue


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
