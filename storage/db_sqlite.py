"""SQLite event storage."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from core.utils import now_timestamp


def connect_event_db(db_path: str) -> sqlite3.Connection:
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            event_type TEXT NOT NULL,
            state TEXT NOT NULL,
            payload TEXT
        )
        """
    )
    conn.commit()
    return conn


class EventDB:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn = connect_event_db(self.db_path)

    def log_event(
        self,
        event_type: str,
        state: str,
        payload: dict[str, Any] | None = None,
        ts: str | None = None,
    ) -> int:
        timestamp = ts or now_timestamp()
        payload_json = json.dumps(payload or {}, ensure_ascii=True)
        cursor = self.conn.execute(
            "INSERT INTO events (ts, event_type, state, payload) VALUES (?, ?, ?, ?)",
            (timestamp, event_type, state, payload_json),
        )
        self.conn.commit()
        row_id = cursor.lastrowid
        return int(row_id) if row_id is not None else -1

    def fetch_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id, ts, event_type, state, payload FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self.conn.close()
