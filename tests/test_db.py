import json
from datetime import date

from storage.db_sqlite import EventDB
from storage.reporter import Reporter


def test_log_event_and_fetch_recent_in_memory_db():
    db = EventDB(":memory:")
    try:
        event_id = db.log_event("fall", "FALLEN", payload={"impact": True}, ts="2026-03-20T00:00:00+00:00")
        assert event_id > 0

        rows = db.fetch_recent(limit=5)
        assert len(rows) == 1

        row = rows[0]
        assert row["event_type"] == "fall"
        assert row["state"] == "FALLEN"
        assert json.loads(row["payload"]) == {"impact": True}
    finally:
        db.close()


def test_file_backed_db_creates_parent_directory_and_file(tmp_path):
    db_path = tmp_path / "nested" / "events.db"

    db = EventDB(str(db_path))
    try:
        event_id = db.log_event("state_change", "NORMAL", payload={"source": "test"})
        assert event_id > 0
        rows = db.fetch_recent(limit=1)
    finally:
        db.close()

    assert db_path.exists()
    assert rows[0]["ts"].endswith("+08:00")


def test_reporter_bootstraps_fresh_db_and_writes_header_only(tmp_path):
    db_path = tmp_path / "fresh" / "events.db"
    report_dir = tmp_path / "reports"
    reporter = Reporter(str(db_path), str(report_dir))

    output = reporter.generate_daily_report(day=date(2026, 3, 20))

    assert db_path.exists()
    assert output.exists()
    assert output.read_text(encoding="utf-8").splitlines() == ["ts,event_type,state,payload"]


def test_reporter_reads_rows_written_by_event_db(tmp_path):
    db_path = tmp_path / "events.db"
    report_dir = tmp_path / "reports"

    db = EventDB(str(db_path))
    try:
        db.log_event(
            "fall",
            "FALLEN",
            payload={"impact": True},
            ts="2026-03-20T08:30:00",
        )
    finally:
        db.close()

    reporter = Reporter(str(db_path), str(report_dir))
    output = reporter.generate_daily_report(day=date(2026, 3, 20))
    lines = output.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert lines[0] == "ts,event_type,state,payload"
    assert "2026-03-20T08:30:00,fall,FALLEN," in lines[1]
