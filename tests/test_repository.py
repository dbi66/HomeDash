from src.repository import MonitoringRepository


def test_repository_reads_latest_monitoring_data(tmp_path) -> None:
    database_path = tmp_path / "test.db"
    repository = MonitoringRepository(database_path)

    assert repository.latest_timestamps() == {"homematic": None, "viessmann": None}
    assert repository.latest_viessmann() == []
    assert repository.viessmann_features() == []
