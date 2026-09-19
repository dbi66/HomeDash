from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from src.viessmann_provider import ViessmannProviderError, load_client
from src.feature_access import FeatureAccessor


@dataclass(frozen=True)
class HeatPumpSnapshot:
    device_id: str
    model: str
    online: bool
    features: dict[str, Any]


def _is_heat_pump(device: Any) -> bool:
    roles = {str(role).lower() for role in getattr(device, "getRoles", lambda: [])()}
    device_type = str(getattr(device, "getDeviceType", lambda: "")()).lower()
    model = str(getattr(device, "getModel", lambda: "")()).lower()
    return (
        "type:heatpump" in roles
        or device_type == "heating" and ("vitocal" in model or "heatpump" in model)
    )


def read_heat_pumps(client: Any) -> list[HeatPumpSnapshot]:
    snapshots: list[HeatPumpSnapshot] = []
    for device in getattr(client, "devices", []):
        if not _is_heat_pump(device):
            continue
        try:
            raw_features = device.get_raw_json()
        except Exception as error:
            raise ViessmannProviderError(
                f"Could not read heat-pump features for {device.getId()}: {error}"
            ) from error
        snapshots.append(
            HeatPumpSnapshot(
                device_id=str(device.getId()),
                model=str(device.getModel()),
                online=bool(device.isOnline()),
                features=raw_features if isinstance(raw_features, dict) else {"data": raw_features},
            )
        )
    if not snapshots:
        raise ViessmannProviderError("No Viessmann heat-pump devices were found")
    return snapshots


def read_heat_pump_information(
    username: str = "",
    password: str = "",
    client_id: str = "",
    token_file: str = "",
) -> list[HeatPumpSnapshot]:
    """Read heat-pump feature data without calling any Viessmann write API."""
    return read_heat_pumps(load_client(username, password, client_id, token_file))


def heat_pump_snapshots_from_inventory(inventory: list[dict[str, Any]]) -> list[HeatPumpSnapshot]:
    return [
        HeatPumpSnapshot(
            device_id=str(device["id"]),
            model=str(device["model"]),
            online=bool(device["online"]),
            features=device["features"] if isinstance(device["features"], dict) else {"data": device["features"]},
        )
        for device in inventory
        if "vitocal" in str(device.get("model", "")).lower()
        or "heatpump" in str(device.get("model", "")).lower()
    ]


def feature_values(snapshot: HeatPumpSnapshot) -> list[dict[str, str]]:
    """Flatten read-only feature properties for display in the dashboard."""
    rows: list[dict[str, str]] = []
    for feature in snapshot.features.get("data", []):
        if not isinstance(feature, dict):
            continue
        feature_name = str(feature.get("feature", ""))
        properties = feature.get("properties", {})
        if not isinstance(properties, dict):
            continue
        for property_name, property_data in properties.items():
            value = property_data.get("value") if isinstance(property_data, dict) else property_data
            unit = property_data.get("unit", "") if isinstance(property_data, dict) else ""
            if isinstance(value, dict) and "value" in value:
                unit = value.get("unit", unit)
                value = value["value"]
            if isinstance(value, (dict, list)):
                value_text = str(value)
            else:
                value_text = "" if value is None else str(value)
            rows.append(
                {
                    "feature": feature_name,
                    "property": str(property_name),
                    "value": value_text,
                    "unit": str(unit),
                }
            )
    return rows


def human_label(value: str) -> str:
    labels = {
        "active": "Aktiv",
        "boiler": "Wärmeerzeuger",
        "buffer": "Puffer",
        "buffer Cylinder": "Pufferspeicher",
        "circulation": "Zirkulation",
        "circuits": "Heizkreis",
        "common Supply": "Gemeinsamer Vorlauf",
        "compressor": "Verdichter",
        "configuration": "Konfiguration",
        "consumption": "Verbrauch",
        "cooling": "Kühlen",
        "current": "Aktuell",
        "dhw": "Warmwasser",
        "dewpoint": "Taupunkt",
        "demand": "Anforderung",
        "energy": "Energie",
        "heating": "Heizen",
        "humidity": "Feuchtigkeit",
        "main": "Hauptwert",
        "mode": "Betriebsart",
        "operating": "Betrieb",
        "outside": "Außen",
        "power": "Leistung",
        "pressure": "Druck",
        "production": "Erzeugung",
        "programs": "Programme",
        "pump": "Pumpe",
        "room": "Raum",
        "sensors": "Sensoren",
        "status": "Status",
        "supply": "Vorlauf",
        "temperature": "Temperatur",
        "value": "Wert",
        "zone": "Zone",
    }
    value = re.sub(r"([a-z])([A-Z])", r"\1 \2", value.replace("_", " "))
    parts = value.split(".")
    translated: list[str] = []
    for part in parts:
        circuit_match = re.fullmatch(r"circuits\s+(\d+)", part)
        if circuit_match:
            translated.append(f"Heizkreis {int(circuit_match.group(1)) + 1}")
        else:
            translated.append(labels.get(part, part.replace("-", " ").capitalize()))
    return " / ".join(translated).strip()


def report_sections(snapshot: HeatPumpSnapshot) -> dict[str, list[dict[str, str]]]:
    sections: dict[str, list[dict[str, str]]] = {
        "Status & Betrieb": [],
        "Temperaturen & Sensoren": [],
        "Heizkreise": [],
        "Warmwasser": [],
        "Energie": [],
        "Weitere Daten": [],
    }
    for row in feature_values(snapshot):
        feature = row["feature"]
        lowered = feature.lower()
        if "circuits" in lowered:
            section = "Heizkreise"
        elif ".dhw" in lowered or "domestichotwater" in lowered:
            section = "Warmwasser"
        elif any(term in lowered for term in ("power", "consumption", "production", "energy")):
            section = "Energie"
        elif any(term in lowered for term in ("temperature", "pressure", "humidity", "sensors")):
            section = "Temperaturen & Sensoren"
        elif any(term in lowered for term in ("status", "operating", "mode", "pump", "compressor", "message")):
            section = "Status & Betrieb"
        else:
            section = "Weitere Daten"
        sections[section].append(
            {
                "name": f"{human_label(feature)} / {human_label(row['property'])}",
                "value": row["value"],
                "unit": row["unit"],
                "feature": feature,
                "property": row["property"],
            }
        )
    return {name: rows for name, rows in sections.items() if rows}


def _feature_property(snapshot: HeatPumpSnapshot, feature_name: str, property_name: str) -> str:
    accessor = FeatureAccessor(snapshot.features)
    value = accessor.value(feature_name, property_name)
    if value is None:
        return "nicht verfügbar"
    for row in feature_values(snapshot):
        if row["feature"] == feature_name and row["property"] == property_name:
            return f"{value} {row['unit']}".strip()
    return str(value)


def system_map(snapshot: HeatPumpSnapshot) -> dict[str, list[dict[str, str]]]:
    """Return the live sensors and actors used by the system overview."""
    return {
        "Außeneinheit": [
            {
                "name": "Außenlüfter 1",
                "value": _feature_property(snapshot, "heating.primaryCircuit.fans.0.current", "value"),
                "state": _feature_property(snapshot, "heating.primaryCircuit.fans.0.current", "status"),
            },
            {
                "name": "Außenlüfter 2",
                "value": _feature_property(snapshot, "heating.primaryCircuit.fans.1.current", "value"),
                "state": _feature_property(snapshot, "heating.primaryCircuit.fans.1.current", "status"),
            },
            {
                "name": "Lüfterring",
                "value": "",
                "state": _feature_property(snapshot, "heating.heater.fanRing", "active"),
            },
        ],
        "Inneneinheit": [
            {
                "name": "Inneneinheit Pumpe",
                "value": _feature_property(snapshot, "heating.boiler.pumps.internal.current", "value"),
                "state": _feature_property(snapshot, "heating.boiler.pumps.internal", "status"),
            },
            {
                "name": "Inneneinheit Heizstab",
                "value": "",
                "state": _feature_property(snapshot, "heating.heatingRod", "active"),
            },
        ],
        "Umgebung": [
            {
                "name": "Außentemperatur",
                "value": _feature_property(snapshot, "heating.sensors.temperature.outside", "value"),
                "state": _feature_property(snapshot, "heating.sensors.temperature.outside", "status"),
            }
        ],
        "Wärmepumpe": [
            {
                "name": "Verdichter",
                "value": _feature_property(snapshot, "heating.compressors.0", "phase"),
                "state": _feature_property(snapshot, "heating.compressors.0", "active"),
            },
            {
                "name": "Heizstab",
                "value": "",
                "state": _feature_property(snapshot, "heating.heatingRod", "active"),
            },
            {
                "name": "Interne Pumpe",
                "value": _feature_property(snapshot, "heating.boiler.pumps.internal.current", "value"),
                "state": _feature_property(snapshot, "heating.boiler.pumps.internal", "status"),
            },
        ],
        "Hydraulik": [
            {
                "name": "Gemeinsamer Vorlauf",
                "value": _feature_property(snapshot, "heating.boiler.sensors.temperature.commonSupply", "value"),
                "state": _feature_property(snapshot, "heating.boiler.sensors.temperature.commonSupply", "status"),
            },
            {
                "name": "Heizungsrücklauf",
                "value": _feature_property(snapshot, "heating.sensors.temperature.return", "value"),
                "state": _feature_property(snapshot, "heating.sensors.temperature.return", "status"),
            },
            {
                "name": "Pufferspeicher",
                "value": _feature_property(snapshot, "heating.bufferCylinder.sensors.temperature.main", "value"),
                "state": _feature_property(snapshot, "heating.bufferCylinder.sensors.temperature.main", "status"),
            },
        ],
        "Heizkreis": [
            {
                "name": "Heizkreis 1 Pumpe",
                "value": _feature_property(snapshot, "heating.circuits.0.operating.modes.active", "value"),
                "state": _feature_property(snapshot, "heating.circuits.0.circulation.pump", "status"),
            },
            {
                "name": "Heizkreis 1 Vorlauf",
                "value": _feature_property(snapshot, "heating.circuits.0.sensors.temperature.supply", "value"),
                "state": _feature_property(snapshot, "heating.circuits.0.operating.programs.active", "value"),
            },
        ],
        "Warmwasser": [
            {
                "name": "Warmwasser",
                "value": _feature_property(snapshot, "heating.dhw.sensors.temperature.dhwCylinder", "value"),
                "state": _feature_property(snapshot, "heating.dhw", "status"),
            },
            {
                "name": "Warmwasser-Zirkulation",
                "value": _feature_property(snapshot, "heating.dhw.operating.modes.active", "value"),
                "state": _feature_property(snapshot, "heating.dhw.pumps.circulation", "status"),
            },
        ],
    }
