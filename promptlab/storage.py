from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "promptlab.db"

BASE_COLUMNS = {
    "created_at": "TEXT NOT NULL", "task_name": "TEXT NOT NULL", "function_name": "TEXT NOT NULL",
    "provider": "TEXT NOT NULL", "model": "TEXT NOT NULL", "technique_key": "TEXT NOT NULL",
    "technique_name": "TEXT NOT NULL", "prompt": "TEXT NOT NULL", "generated_code": "TEXT NOT NULL",
    "status": "TEXT NOT NULL", "task_passed": "INTEGER", "passed_tests": "INTEGER NOT NULL DEFAULT 0",
    "total_tests": "INTEGER NOT NULL DEFAULT 0", "latency_seconds": "REAL", "prompt_tokens": "INTEGER",
    "completion_tokens": "INTEGER", "test_results_json": "TEXT NOT NULL DEFAULT '[]'", "error_message": "TEXT",
}
# Added in v2; older databases are migrated automatically.
NEW_COLUMNS = {
    "run_id": "TEXT", "user_request": "TEXT", "trial": "INTEGER", "exec_ms": "REAL", "adj_passed": "INTEGER",
    "adj_total": "INTEGER", "rounds": "INTEGER", "exec_mode": "TEXT", "score": "REAL",
}
COLUMNS = list(BASE_COLUMNS) + list(NEW_COLUMNS)


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


def initialize() -> None:
    with connect() as connection:
        defs = ", ".join(f"{name} {kind}" for name, kind in {**BASE_COLUMNS, **NEW_COLUMNS}.items())
        connection.execute(f"CREATE TABLE IF NOT EXISTS experiments (id INTEGER PRIMARY KEY AUTOINCREMENT, {defs})")
        existing = {row["name"] for row in connection.execute("PRAGMA table_info(experiments)")}
        for name, kind in NEW_COLUMNS.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE experiments ADD COLUMN {name} {kind.replace(' NOT NULL', '')}")
        connection.commit()


def save_experiment(record: dict[str, Any]) -> int:
    initialize()
    record = dict(record)
    record.setdefault("created_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    record["test_results_json"] = json.dumps(record.pop("test_results", []), ensure_ascii=False, default=repr)
    for text_col in ("provider", "model", "generated_code"):
        record[text_col] = record.get(text_col) or ""
    values = [record.get(column) for column in COLUMNS]
    with connect() as connection:
        cursor = connection.execute(
            f"INSERT INTO experiments ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})", values)
        connection.commit()
        return int(cursor.lastrowid)


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["test_results"] = json.loads(item.pop("test_results_json", "[]") or "[]")
    return item


def get_experiments(limit: int = 2000) -> list[dict[str, Any]]:
    initialize()
    with connect() as connection:
        rows = connection.execute("SELECT * FROM experiments ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
    return [_decode(row) for row in rows]


def get_experiment(experiment_id: int) -> dict[str, Any] | None:
    initialize()
    with connect() as connection:
        row = connection.execute("SELECT * FROM experiments WHERE id = ?", (int(experiment_id),)).fetchone()
    return _decode(row) if row else None


def delete_all_experiments() -> None:
    initialize()
    with connect() as connection:
        connection.execute("DELETE FROM experiments")
        connection.commit()


def reserve_usage_slot(limit: int = 6, window_minutes: int = 60) -> tuple[bool, int]:
    """Atomically reserve one app run from a global per-instance rolling-window quota.

    This protects one running app instance from accidental/ordinary overuse. It is not a
    substitute for provider-side quotas or platform-level authentication.
    """
    if limit < 1 or window_minutes < 1:
        raise ValueError("Quota limit and window must be positive.")
    initialize()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=window_minutes)).isoformat(timespec="seconds")
    retention = (now - timedelta(days=1)).isoformat(timespec="seconds")
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL
            )"""
        )
        connection.execute("DELETE FROM usage_events WHERE created_at < ?", (retention,))
        used = int(connection.execute(
            "SELECT COUNT(*) FROM usage_events WHERE created_at >= ?", (cutoff,)
        ).fetchone()[0])
        if used >= limit:
            connection.commit()
            return False, 0
        connection.execute("INSERT INTO usage_events (created_at) VALUES (?)", (now.isoformat(timespec="seconds"),))
        connection.commit()
        return True, max(0, limit - used - 1)
