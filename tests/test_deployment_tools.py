import sqlite3
from pathlib import Path

from scripts.backup_database import main as backup_main


def test_backup_verify_creates_integrity_checked_copy(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "backup.db"
    with sqlite3.connect(source) as connection:
        connection.execute("create table sample (value integer)")
        connection.execute("insert into sample values (1)")

    monkeypatch.setattr("scripts.backup_database.DATABASE_PATH", source)
    monkeypatch.setattr("scripts.backup_database.sys.argv", ["backup_database.py", "--output", str(target), "--verify"])

    assert backup_main() == 0
    with sqlite3.connect(target) as connection:
        assert connection.execute("pragma integrity_check").fetchone()[0] == "ok"
