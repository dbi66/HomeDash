from __future__ import annotations

from typing import Any


class FeatureAccessor:
    """Safe, centralized access to PyViCare's flattened raw feature payload."""

    def __init__(self, features: dict[str, Any]):
        self._features = features

    def value(self, feature_name: str, property_name: str) -> Any:
        for feature in self._features.get("data", []):
            if not isinstance(feature, dict) or feature.get("feature") != feature_name:
                continue
            properties = feature.get("properties", {})
            if not isinstance(properties, dict):
                return None
            property_data = properties.get(property_name)
            if isinstance(property_data, dict):
                value = property_data.get("value")
                return value.get("value") if isinstance(value, dict) else value
            return property_data
        return None

    def text(self, feature_name: str, property_name: str, default: str = "") -> str:
        value = self.value(feature_name, property_name)
        return default if value is None else str(value)
