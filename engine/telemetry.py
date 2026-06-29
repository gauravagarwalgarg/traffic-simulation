"""
Telemetry ingestion worker: consumes buffer, writes to SQLite for thesis queries.
Runs in a background thread, batches writes for efficiency.
"""
from __future__ import annotations
import sqlite3
import threading
import time
from typing import Optional, Callable
from engine.models import TelemetryRecord


class TelemetryWriter:
    """Background thread that drains simulation telemetry into SQLite."""

    def __init__(self, db_path: str = "telemetry.db", batch_interval: float = 1.0):
        self.db_path = db_path
        self.batch_interval = batch_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._drain_fn: Optional[Callable] = None
        self._total_records: int = 0

    def start(self, drain_fn: Callable[[], list[TelemetryRecord]]) -> None:
        """Start background writer. drain_fn returns list[TelemetryRecord]."""
        self._drain_fn = drain_fn
        self._running = True
        self._total_records = 0
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background writer and flush remaining data."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        # Final flush in main thread with its own connection
        self._flush_final()

    def _run_loop(self) -> None:
        """Background thread: create connection HERE (same thread that uses it)."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                timestamp REAL,
                vehicle_id INTEGER,
                vehicle_type TEXT,
                x REAL, y REAL,
                speed REAL,
                acceleration REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON telemetry(timestamp)")
        conn.commit()

        while self._running:
            time.sleep(self.batch_interval)
            self._flush_to(conn)

        # One last flush before thread exits
        self._flush_to(conn)
        conn.close()

    def _flush_to(self, conn: sqlite3.Connection) -> None:
        if not self._drain_fn:
            return
        records = self._drain_fn()
        if not records:
            return
        conn.executemany(
            "INSERT INTO telemetry VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(r.timestamp, r.vehicle_id, r.vehicle_type, r.x, r.y, r.speed, r.acceleration)
             for r in records]
        )
        conn.commit()
        self._total_records += len(records)

    def _flush_final(self) -> None:
        """Final flush from main thread after background thread has stopped."""
        if not self._drain_fn:
            return
        records = self._drain_fn()
        if not records:
            return
        conn = sqlite3.connect(self.db_path)
        conn.executemany(
            "INSERT INTO telemetry VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(r.timestamp, r.vehicle_id, r.vehicle_type, r.x, r.y, r.speed, r.acceleration)
             for r in records]
        )
        conn.commit()
        self._total_records += len(records)
        conn.close()

    @property
    def record_count(self) -> int:
        return self._total_records
