from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeAlias


RoomValue: TypeAlias = str | float | int | bool | None


@dataclass(frozen=True)
class RoomReading:
    room_name: str
    current_temperature: float
    target_temperature: float
    humidity: float
    valve_position: float
    recorded_at: datetime
    level: str = "Unassigned"


@dataclass(frozen=True)
class FeatureValue:
    feature: str
    property: str
    value: RoomValue
    unit: str = ""

    @classmethod
    def from_raw(cls, feature: dict[str, Any], property_name: str) -> "FeatureValue":
        properties = feature.get("properties", {})
        raw_value = properties.get(property_name, {}) if isinstance(properties, dict) else {}
        value = raw_value.get("value") if isinstance(raw_value, dict) else raw_value
        unit = raw_value.get("unit", "") if isinstance(raw_value, dict) else ""
        if isinstance(value, dict) and "value" in value:
            unit = str(value.get("unit", unit))
            value = value["value"]
        return cls(
            feature=str(feature.get("feature", "")),
            property=str(property_name),
            value=value,
            unit=str(unit),
        )

    def __getitem__(self, key: str) -> Any:
        return {"feature": self.feature, "property": self.property, "value": self.value, "unit": self.unit}[key]


@dataclass(frozen=True)
class HeatPumpSnapshot:
    device_id: str
    model: str
    online: bool
    features: dict[str, Any]
