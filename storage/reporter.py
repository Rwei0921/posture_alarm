"""CSV report generator based on SQLite events."""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

from storage.db_sqlite import connect_event_db


class Reporter:
    def __init__(self, db_path: str, output_dir: str) -> None:
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_daily_report(self, day: date | None = None) -> Path:
        target_day = day or date.today()
        start = datetime.combine(target_day, datetime.min.time())
        end = start + timedelta(days=1)
        rows = self._fetch_range(start.isoformat(), end.isoformat())
        output = self.output_dir / f"daily_{target_day.isoformat()}.csv"
        self._write_csv(output, rows)
        return output

    def generate_weekly_report(self, day: date | None = None) -> Path:
        target_day = day or date.today()
        week_start = target_day - timedelta(days=target_day.weekday())
        start = datetime.combine(week_start, datetime.min.time())
        end = start + timedelta(days=7)
        rows = self._fetch_range(start.isoformat(), end.isoformat())
        output = self.output_dir / f"weekly_{week_start.isoformat()}.csv"
        self._write_csv(output, rows)
        return output

    def _fetch_range(self, start_iso: str, end_iso: str) -> list[dict[str, str]]:
        conn = connect_event_db(self.db_path)
        try:
            rows = conn.execute(
                """
                SELECT ts, event_type, state, payload
                FROM events
                WHERE ts >= ? AND ts < ?
                ORDER BY ts ASC
                """,
                (start_iso, end_iso),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=["ts", "event_type", "state", "payload"])
            writer.writeheader()
            writer.writerows(rows)
