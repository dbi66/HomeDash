from collections import defaultdict
from typing import Iterable


BASE_LEVEL = "Erdgeschoss"
UPSTAIRS = "Obergeschoss"
UNASSIGNED = "Nicht zugeordnet"

ROOM_LEVELS = {
    "Arbeit Dennis": BASE_LEVEL,
    "Wohnzimmer": UPSTAIRS,
}

ROOM_ALIASES = {
    "Bedroom": "Schlafzimmer",
    "Kitchen": "Küche",
    "Küche": "Küche",
    "Living Room": "Wohnzimmer",
    "Wohnzimmer": "Wohnzimmer",
}


def level_from_controller_devices(devices: Iterable[object]) -> str:
    labels = [str(getattr(device, "label", "")).lower() for device in devices]
    has_upstairs = any(" oben" in label or label.endswith("oben") for label in labels)
    has_base_level = any(" unten" in label or label.endswith("unten") for label in labels)
    if has_upstairs and not has_base_level:
        return UPSTAIRS
    if has_base_level and not has_upstairs:
        return BASE_LEVEL
    return UNASSIGNED


def canonical_room_name(room_name: str) -> str:
    return ROOM_ALIASES.get(room_name.strip(), room_name.strip())


def group_readings_by_level(readings: Iterable[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for reading in readings:
        room_name = canonical_room_name(str(reading["room_name"]))
        level = str(reading.get("level") or ROOM_LEVELS.get(room_name, UNASSIGNED))
        grouped[level].append({**reading, "room_name": room_name})
    return dict(grouped)
