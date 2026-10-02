import json
import sqlite3
from pathlib import Path
from typing import Any

from argus.core.timeline import build_timeline
from argus.models.alert import Alert
from argus.models.event import Event


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    src_ip TEXT,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_ip_time ON events(src_ip, timestamp);
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    src_ip TEXT,
                    risk_score INTEGER NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS alerts_time ON alerts(timestamp);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def record_event(self, event: Event) -> None:
        payload = event.to_dict()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO events (id, timestamp, src_ip, payload) VALUES (?, ?, ?, ?)",
                (event.event_id, payload["timestamp"], event.src_ip, json.dumps(payload, sort_keys=True)),
            )

    def record_alert(self, alert: Alert) -> None:
        payload = alert.to_dict()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO alerts (id, event_id, timestamp, src_ip, risk_score, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    alert.alert_id,
                    alert.event_id,
                    alert.timestamp,
                    alert.src_ip,
                    alert.risk_score,
                    json.dumps(payload, sort_keys=True),
                ),
            )

    def list_alerts(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 500))
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM alerts ORDER BY timestamp DESC LIMIT ?", (safe_limit,)
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def timeline(self, src_ip: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 2000))
        with self._connect() as connection:
            if src_ip:
                event_rows = connection.execute(
                    "SELECT payload FROM events WHERE src_ip = ? ORDER BY timestamp DESC LIMIT ?",
                    (src_ip, safe_limit),
                ).fetchall()
                alert_rows = connection.execute(
                    "SELECT payload FROM alerts WHERE src_ip = ? ORDER BY timestamp DESC LIMIT ?",
                    (src_ip, safe_limit),
                ).fetchall()
            else:
                event_rows = connection.execute(
                    "SELECT payload FROM events ORDER BY timestamp DESC LIMIT ?", (safe_limit,)
                ).fetchall()
                alert_rows = connection.execute(
                    "SELECT payload FROM alerts ORDER BY timestamp DESC LIMIT ?", (safe_limit,)
                ).fetchall()
        events = [json.loads(row["payload"]) for row in event_rows]
        alerts = [json.loads(row["payload"]) for row in alert_rows]
        return build_timeline(events, alerts)