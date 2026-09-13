from datetime import datetime, timezone

from src.models import RoomReading


MOCK_ROOMS = (
    ("Living Room", 21.4, 21.0, 46.0, 38.0),
    ("Kitchen", 20.8, 21.0, 49.0, 52.0),
    ("Bedroom", 19.6, 19.0, 44.0, 24.0),
)


def get_room_readings() -> list[RoomReading]:
    recorded_at = datetime.now(timezone.utc)
    return [
        RoomReading(
            room_name=room_name,
            current_temperature=current_temperature,
            target_temperature=target_temperature,
            humidity=humidity,
            valve_position=valve_position,
            recorded_at=recorded_at,
        )
        for room_name, current_temperature, target_temperature, humidity, valve_position in MOCK_ROOMS
    ]
