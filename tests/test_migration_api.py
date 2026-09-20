from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.database import initialize_database, save_readings
from src.models import RoomReading


def test_migration_api_reads_room_data_without_provider_access(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "migration.db"
    initialize_database(database_path)
    save_readings(
        database_path,
        [
            RoomReading(
                room_name="Wohnzimmer",
                current_temperature=21.5,
                target_temperature=21.0,
                humidity=52.0,
                valve_position=20.0,
                recorded_at=datetime.now(timezone.utc),
                level="Erdgeschoss",
            )
        ],
    )
    monkeypatch.setenv("HOMEDASH_DATABASE", str(database_path))

    from migration.api import app

    client = TestClient(app)
    response = client.get("/api/v1/rooms")

    assert response.status_code == 200
    assert response.json()[0]["room_name"] == "Wohnzimmer"
    assert response.json()[0]["current_temperature"] == 21.5


def test_migration_api_reports_database_readiness(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "migration.db"
    initialize_database(database_path)
    monkeypatch.setenv("HOMEDASH_DATABASE", str(database_path))

    from migration.api import app

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["database"] == "read-only"
