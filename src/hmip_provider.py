import configparser
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Union

from homematicip.home import Home

from src.config import CONFIG_PATH
from src.models import RoomReading
from src.room_layout import ROOM_LEVELS, canonical_room_name, level_from_controller_devices


class HomematicProviderError(RuntimeError):
    """Raised when Homematic IP data cannot be loaded or mapped."""


def _number(device: object, *names: str) -> Optional[float]:
    for name in names:
        value = getattr(device, name, None)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _percent(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, min(100.0, value * 100 if value <= 1 else value))


def _room_groups(home: Home) -> Iterable[object]:
    room_groups = [
        group
        for group in home.groups
        if getattr(group, "groupType", None) in {"HEATING", "INDOOR_CLIMATE"}
        and getattr(group, "metaGroup", None) is not None
    ]
    return room_groups


def map_room_readings(home: Home) -> list[RoomReading]:
    recorded_at = datetime.now(timezone.utc)
    readings: list[RoomReading] = []
    grouped_devices: dict[tuple[str, str], list[object]] = {}
    grouped_valves: dict[tuple[str, str], list[float]] = {}

    for group in _room_groups(home):
        room_name = canonical_room_name(getattr(group, "label", None) or "Unnamed room")
        devices = getattr(group, "devices", [])
        level = ROOM_LEVELS.get(room_name, level_from_controller_devices(devices))
        group_key = (room_name, level)
        grouped_devices.setdefault(group_key, []).extend(devices)
        for device in devices:
            for channel in getattr(device, "functionalChannels", []):
                valve = _percent(_number(channel, "valvePosition"))
                channel_groups = getattr(channel, "groups", [])
                belongs_to_group = any(
                    getattr(channel_group, "id", None) == getattr(group, "id", None)
                    for channel_group in channel_groups
                )
                if valve is not None and belongs_to_group:
                    grouped_valves.setdefault(group_key, []).append(valve)

    for (room_name, level), devices in grouped_devices.items():
        temperatures: list[float] = []
        targets: list[float] = []
        humidities: list[float] = []
        valves: list[float] = grouped_valves.get((room_name, level), []).copy()
        seen_devices: set[str] = set()

        for device in devices:
            device_id = str(getattr(device, "id", id(device)))
            if device_id in seen_devices:
                continue
            seen_devices.add(device_id)

            temperature = _number(device, "actualTemperature", "valveActualTemperature")
            if temperature is not None:
                temperatures.append(temperature)

            target = _number(device, "setPointTemperature")
            if target is not None:
                targets.append(target)

            humidity = _number(device, "humidity")
            if humidity is not None:
                humidities.append(humidity)

            valve = _percent(_number(device, "valvePosition"))
            if valve is not None:
                valves.append(valve)

        if not temperatures:
            continue

        current_temperature = sum(temperatures) / len(temperatures)
        readings.append(
            RoomReading(
                room_name=room_name,
                current_temperature=current_temperature,
                target_temperature=sum(targets) / len(targets) if targets else current_temperature,
                humidity=sum(humidities) / len(humidities) if humidities else 0.0,
                valve_position=sum(valves) / len(valves) if valves else 0.0,
                recorded_at=recorded_at,
                level=level,
            )
        )

    return readings


def load_home(config_path: Union[str, Path] = CONFIG_PATH) -> Home:
    config = configparser.ConfigParser()
    path = Path(config_path)
    if not path.exists():
        raise HomematicProviderError(f"Homematic config not found: {path}")

    config.read(path)
    try:
        access_point = config["AUTH"]["accesspoint"]
        auth_token = config["AUTH"]["authtoken"]
    except KeyError as error:
        raise HomematicProviderError("Homematic config is missing required auth fields") from error

    home = Home()
    try:
        home.init(access_point)
        home.set_auth_token(auth_token)
        if home.get_current_state(clearConfig=True) is False:
            raise HomematicProviderError("Homematic IP returned no current state")
    except HomematicProviderError:
        raise
    except Exception as error:
        raise HomematicProviderError(f"Homematic IP connection failed: {error}") from error
    return home


def get_room_readings(config_path: Union[str, Path] = CONFIG_PATH) -> list[RoomReading]:
    readings = map_room_readings(load_home(config_path))
    if not readings:
        raise HomematicProviderError("No room temperature devices were found")
    return readings
