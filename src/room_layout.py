from collections import defaultdict
from typing import Iterable


BASE_LEVEL = "Base level"
UPSTAIRS = "Upstairs"
UNASSIGNED = "Unassigned"

ROOM_LEVELS = {
    "Arbeit Dennis": BASE_LEVEL,
    "Living Room": UPSTAIRS,
}


def group_readings_by_level(readings: Iterable[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for reading in readings:
        room_name = str(reading["room_name"])
        grouped[ROOM_LEVELS.get(room_name, UNASSIGNED)].append(reading)
    return dict(grouped)
