from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RoomReading:
    room_name: str
    current_temperature: float
    target_temperature: float
    humidity: float
    valve_position: float
    recorded_at: datetime
    level: str = "Unassigned"
