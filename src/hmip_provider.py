import configparser
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Union

from homematicip.home import Home

from src.models import RoomReading
from src.room_layout import ROOM_LEVELS, canonical_room_name, level_from_controller_devices


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.ini"


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

    for group in _room_groups(home):
        room_name = canonical_room_name(getattr(group, "label", None) or "Unnamed room")
        devices = getattr(group, "devices", [])
        level = ROOM_LEVELS.get(room_name, level_from_controller_devices(devices))
        grouped_devices.setdefault((room_name, level), []).extend(devices)

    for (room_name, level), devices in grouped_devices.items():
        temperatures: list[float] = []
        targets: list[float] = []
        humidities: list[float] = []
        valves: list[float] = []
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


def set_room_target_temperature(
    home: Home,
    room_name: str,
    temperature: float,
) -> object:
    if not 5.0 <= temperature <= 35.0:
        raise HomematicProviderError("Target temperature must be between 5.0 C and 35.0 C")

    canonical_name = canonical_room_name(room_name)
    candidates = [
        group
        for group in home.groups
        if getattr(group, "groupType", None) == "HEATING"
        and canonical_room_name(getattr(group, "label", "")) == canonical_name
    ]
    if not candidates:
        raise HomematicProviderError(f"No Homematic heating group found for {canonical_name}")

    group = candidates[0]
    if getattr(group, "controllable", True) is False:
        raise HomematicProviderError(f"{canonical_name} is not controllable")
    setter = getattr(group, "set_point_temperature", None)
    if setter is None:
        raise HomematicProviderError(f"{canonical_name} does not support target changes")
    response = setter(round(temperature, 1))
    if isinstance(response, dict) and response.get("errorCode"):
        raise HomematicProviderError(f"Homematic rejected the target change: {response['errorCode']}")
    return response
