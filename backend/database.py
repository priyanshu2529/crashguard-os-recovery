import sqlite3
from pathlib import Path
from typing import Any

from . import config


class Database:
    def __init__(self, db_path: Path = config.DB_PATH) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    checkpoint_id TEXT UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    state_size INTEGER NOT NULL,
                    checkpoint_type TEXT NOT NULL,
                    process_id INTEGER,
                    status TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    snapshot_path TEXT NOT NULL,
                    base_checkpoint_id INTEGER,
                    storage_savings REAL DEFAULT 0,
                    validation_reason TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON checkpoints(status);

                CREATE TABLE IF NOT EXISTS recovery_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    failure_type TEXT NOT NULL,
                    failure_time TEXT NOT NULL,
                    detection_time TEXT NOT NULL,
                    recovery_start TEXT NOT NULL,
                    recovery_end TEXT NOT NULL,
                    recovery_duration REAL NOT NULL,
                    rto REAL NOT NULL,
                    checkpoint_used TEXT,
                    recovery_status TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    checkpoint_id TEXT,
                    status TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON system_events(timestamp);

                CREATE TABLE IF NOT EXISTS configuration (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            defaults = [
                ("recovery_policy", config.DEFAULT_POLICY),
                ("monitor_interval_seconds", str(config.MONITOR_INTERVAL_SECONDS)),
                ("heartbeat_timeout_seconds", str(config.HEARTBEAT_TIMEOUT_SECONDS)),
                ("cpu_threshold_percent", str(config.CPU_THRESHOLD_PERCENT)),
                ("memory_threshold_mb", str(config.MEMORY_THRESHOLD_MB)),
            ]
            for k, v in defaults:
                conn.execute(
                    "INSERT OR IGNORE INTO configuration(key, value) VALUES(?, ?)",
                    (k, v),
                )

    def rows(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def row(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> int:
        with self.connect() as conn:
            cur = conn.execute(query, params)
            conn.commit()
            return int(cur.lastrowid)
