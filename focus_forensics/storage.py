from __future__ import annotations

import sqlite3
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS activity_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    window_title TEXT NOT NULL,
                    process_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    keyboard_events INTEGER NOT NULL,
                    mouse_events INTEGER NOT NULL,
                    idle_seconds REAL NOT NULL,
                    is_idle INTEGER NOT NULL,
                    sample_seconds REAL NOT NULL
                );
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_samples(ts);"
            )

    def insert_sample(
        self,
        ts: str,
        window_title: str,
        process_name: str,
        category: str,
        keyboard_events: int,
        mouse_events: int,
        idle_seconds: float,
        is_idle: bool,
        sample_seconds: float,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO activity_samples (
                    ts, window_title, process_name, category,
                    keyboard_events, mouse_events, idle_seconds, is_idle, sample_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    ts,
                    window_title,
                    process_name,
                    category,
                    keyboard_events,
                    mouse_events,
                    idle_seconds,
                    1 if is_idle else 0,
                    sample_seconds,
                ),
            )

    def get_samples_for_day(self, target_day: date) -> list[dict[str, Any]]:
        like = target_day.isoformat() + "%"
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM activity_samples WHERE ts LIKE ? ORDER BY ts ASC;",
                (like,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recent_samples(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM activity_samples ORDER BY ts DESC LIMIT ?;",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_samples_between(self, start_day: date, end_day: date) -> list[dict[str, Any]]:
        start_ts = start_day.isoformat()
        end_ts = (end_day + timedelta(days=1)).isoformat()
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT *
                FROM activity_samples
                WHERE ts >= ? AND ts < ?
                ORDER BY ts ASC;
                """,
                (start_ts, end_ts),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_all_samples(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM activity_samples;")

    def close(self) -> None:
        with self._lock:
            self._conn.close()
