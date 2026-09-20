from datetime import datetime, timezone

from src.models import RoomReading
from src.repository import MonitoringRepository
from src.database import save_readings


def test_repository_reads_latest_monitoring_data(tmp_path) -> None:
    database_path = tmp_path / "test.db"
    repository = MonitoringRepository(database_path)

    assert repository.latest_timestamps() == {"homematic": None, "viessmann": None}
    assert repository.latest_viessmann() == []
    assert repository.viessmann_features() == []


def test_repository_reads_latest_room_data(tmp_path) -> None:
    database_path = tmp_path / "test.db"
    repository = MonitoringRepository(database_path)
    save_readings(
        database_path,
        [
            RoomReading(
                room_name="Wohnzimmer",
                current_temperature=21.5,
                target_temperature=22.0,
                humidity=44,
                valve_position=50,
                recorded_at=datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc),
                level="Erdgeschoss",
            )
        ],
    )

    rows = repository.latest_room_readings()
    assert len(rows) == 1
    assert rows[0]["room_name"] == "Wohnzimmer"
    assert rows[0]["current_temperature"] == 21.5
