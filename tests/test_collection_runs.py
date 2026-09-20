import sqlite3

from src.database import finish_collection_run, start_collection_run


def test_collection_run_records_success(tmp_path) -> None:
    database_path = tmp_path / "collection-runs.db"

    run_id = start_collection_run(database_path, "homematic", "2026-09-20T12:00:00+00:00")
    finish_collection_run(
        database_path,
        run_id,
        finished_at="2026-09-20T12:00:03+00:00",
        status="success",
        record_count=14,
        duration_ms=3000,
    )

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT provider, status, record_count, duration_ms, error FROM collection_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    assert row == ("homematic", "success", 14, 3000, None)