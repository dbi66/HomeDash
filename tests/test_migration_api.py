from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.database import initialize_database, save_readings, save_viessmann_snapshots
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


def test_migration_api_serves_home_shell() -> None:
    from migration.api import app

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "Migration Dashboard" in response.text


def test_migration_api_serves_frontend_entrypoint() -> None:
    from migration.api import app

    response = TestClient(app).get("/app.js")

    assert response.status_code == 200
    assert "api/v1/home" in response.text


def test_migration_api_home_summary_is_read_only(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "migration.db"
    initialize_database(database_path)
    save_readings(
        database_path,
        [
            RoomReading(
                room_name="Küche",
                current_temperature=22.0,
                target_temperature=21.0,
                humidity=50.0,
                valve_position=0.0,
                recorded_at=datetime.now(timezone.utc),
                level="Erdgeschoss",
            )
        ],
    )
    monkeypatch.setenv("HOMEDASH_DATABASE", str(database_path))

    from migration.api import app

    response = TestClient(app).get("/api/v1/home")

    assert response.status_code == 200
    assert response.json()["room_count"] == 1
    assert response.json()["rooms"][0]["room_name"] == "Küche"


def test_migration_api_returns_room_history(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "migration.db"
    initialize_database(database_path)
    save_readings(
        database_path,
        [
            RoomReading(
                room_name="Wohnzimmer",
                current_temperature=22.0,
                target_temperature=21.0,
                humidity=50.0,
                valve_position=0.0,
                recorded_at=datetime.now(timezone.utc),
                level="Obergeschoss",
            )
        ],
    )
    monkeypatch.setenv("HOMEDASH_DATABASE", str(database_path))

    from migration.api import app

    response = TestClient(app).get("/api/v1/rooms/Wohnzimmer/history?hours=24")

    assert response.status_code == 200
    assert response.json()[0]["current_temperature"] == 22.0


def test_migration_api_returns_heat_pump_report(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "migration.db"
    initialize_database(database_path)
    save_viessmann_snapshots(
        database_path,
        [
            {
                "id": "heat-pump-1",
                "model": "E3_Vitocal_16",
                "online": True,
                "features": {"data": []},
            }
        ],
    )
    monkeypatch.setenv("HOMEDASH_DATABASE", str(database_path))

    from migration.api import app

    response = TestClient(app).get("/api/v1/heat-pump/report")

    assert response.status_code == 200
    assert response.json()["model"] == "E3_Vitocal_16"
    assert "metrics" in response.json()
