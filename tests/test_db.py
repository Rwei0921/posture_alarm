import json

from storage.db_sqlite import EventDB


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
