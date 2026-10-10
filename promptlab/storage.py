from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "promptlab.db"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


def initialize() -> None:
    with connect() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL, task_name TEXT NOT NULL, function_name TEXT NOT NULL,
                provider TEXT NOT NULL, model TEXT NOT NULL, technique_key TEXT NOT NULL,
                technique_name TEXT NOT NULL, prompt TEXT NOT NULL, generated_code TEXT NOT NULL,
                status TEXT NOT NULL, task_passed INTEGER, passed_tests INTEGER NOT NULL DEFAULT 0,
                total_tests INTEGER NOT NULL DEFAULT 0, latency_seconds REAL, prompt_tokens INTEGER,
                completion_tokens INTEGER, test_results_json TEXT NOT NULL DEFAULT '[]', error_message TEXT
            )"""
        )
        connection.commit()


def save_experiment(record: dict[str, Any]) -> int:
    initialize()
    columns = ["created_at", "task_name", "function_name", "provider", "model", "technique_key",
               "technique_name", "prompt", "generated_code", "status", "task_passed", "passed_tests",
               "total_tests", "latency_seconds", "prompt_tokens", "completion_tokens", "test_results_json", "error_message"]
    if "created_at" not in record:
        record["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = dict(record)
    record["test_results_json"] = json.dumps(record.get("test_results", []), ensure_ascii=False)
    record.pop("test_results", None)
    values = [record.get(column) for column in columns]
    with connect() as connection:
        cursor = connection.execute(
            f"INSERT INTO experiments ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})", values
        )
        connection.commit()
        return int(cursor.lastrowid)


def get_experiments(limit: int = 1000) -> list[dict[str, Any]]:
    initialize()
    with connect() as connection:
        rows = connection.execute("SELECT * FROM experiments ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
    output = []
    for row in rows:
        item = dict(row)
        item["test_results"] = json.loads(item.pop("test_results_json", "[]") or "[]")
        output.append(item)
    return output


def get_experiment(experiment_id: int) -> dict[str, Any] | None:
    initialize()
    with connect() as connection:
        row = connection.execute("SELECT * FROM experiments WHERE id = ?", (int(experiment_id),)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["test_results"] = json.loads(item.pop("test_results_json", "[]") or "[]")
    return item


def delete_all_experiments() -> None:
    initialize()
    with connect() as connection:
        connection.execute("DELETE FROM experiments")
        connection.commit()
