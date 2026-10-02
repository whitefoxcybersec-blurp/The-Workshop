from __future__ import annotations

import hashlib
import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_EVIDENCE = [
    ("browser capture", "HTTP", "Access-Control-Allow-Origin: *", "supports", "GET /api/profile · response headers", "2026-09-29T09:58:31+00:00"),
    ("local token review", "JWT", "JWT exp claim presente", "neutral", "Token decodificado localmente · payload", "2026-09-29T09:56:12+00:00"),
    ("certificate metadata", "TLS", "TLS 1.3 negociado", "neutral", "Certificate metadata · observação passiva", "2026-09-29T09:53:04+00:00"),
    ("browser capture", "HTTP", "Cookie sem atributo SameSite", "supports", "Set-Cookie · flags revisadas, valor removido", "2026-09-29T09:51:48+00:00"),
    ("local crypto review", "CRYPTO", "Nonce com entropia aparente", "neutral", "Amostra de 32 bytes · análise local", "2026-09-29T09:49:20+00:00"),
    ("saved JWKS artifact", "JWT", "JWKS publica chave RS256", "neutral", "JWKS já coletado · sem nova requisição", "2026-09-29T09:46:15+00:00"),
    ("browser capture", "HTTP", "HSTS max-age: 31536000", "contradicts", "Strict-Transport-Security · header", "2026-09-29T09:43:50+00:00"),
    ("certificate metadata", "TLS", "Certificado válido por 89 dias", "neutral", "Certificate validity · SAN observado", "2026-09-29T09:41:12+00:00"),
]

DEFAULT_HYPOTHESES = [
    ("cors", "CORS permissivo pode expor dados autenticados", "cors", 0.62, 0.85),
    ("cookie", "Política de cookie pode permitir CSRF", "cookie", 0.50, 0.85),
    ("jwt", "Validação de JWT merece revisão manual", "jwt", 0.35, 0.85),
]


def database_path() -> Path:
    configured = os.environ.get("WOLF_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".local" / "share" / "wolf" / "wolf.sqlite3"


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database_connection() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def initialize_database() -> None:
    with database_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scopes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                root TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(session_id, root)
            );
            CREATE TABLE IF NOT EXISTS hypotheses (
                id TEXT NOT NULL,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                prior REAL NOT NULL,
                report_threshold REAL NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(session_id, id)
            );
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                source TEXT NOT NULL,
                kind TEXT NOT NULL,
                observation TEXT NOT NULL,
                bearing TEXT NOT NULL,
                confidence REAL NOT NULL,
                artifact_hash TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS evidence_session_time
                ON evidence(session_id, observed_at DESC, id DESC);
            CREATE TABLE IF NOT EXISTS hypothesis_evidence (
                session_id TEXT NOT NULL,
                hypothesis_id TEXT NOT NULL,
                evidence_id INTEGER NOT NULL REFERENCES evidence(id),
                PRIMARY KEY(session_id, hypothesis_id, evidence_id),
                FOREIGN KEY(session_id, hypothesis_id) REFERENCES hypotheses(session_id, id)
            );
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                hypothesis_id TEXT NOT NULL,
                title TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'unknown',
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id, hypothesis_id) REFERENCES hypotheses(session_id, id)
            );
            CREATE TABLE IF NOT EXISTS recon_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                event_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            """
        )

        active = connection.execute(
            "SELECT value FROM settings WHERE key = 'active_session_id'"
        ).fetchone()
        if active:
            return

        session_id = str(uuid.uuid4())
        created_at = now_iso()
        connection.execute(
            "INSERT INTO sessions(id, name, created_at) VALUES (?, ?, ?)",
            (session_id, "Hunt 24-091", created_at),
        )
        connection.execute(
            "INSERT INTO settings(key, value) VALUES ('active_session_id', ?)",
            (session_id,),
        )
        connection.execute(
            "INSERT INTO scopes(session_id, root, enabled, created_at) VALUES (?, ?, 1, ?)",
            (session_id, "demo.test", created_at),
        )
        connection.executemany(
            """INSERT INTO hypotheses
               (id, session_id, name, class_name, prior, report_threshold, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (hypothesis_id, session_id, name, class_name, prior, threshold, created_at)
                for hypothesis_id, name, class_name, prior, threshold in DEFAULT_HYPOTHESES
            ],
        )
        for index, (source, kind, observation, bearing, detail, observed_at) in enumerate(
            DEFAULT_EVIDENCE, start=1
        ):
            artifact_hash = hashlib.sha256(f"wolf-demo-{index}".encode()).hexdigest()
            cursor = connection.execute(
                """INSERT INTO evidence
                   (session_id, source, kind, observation, bearing, confidence,
                    artifact_hash, observed_at, detail, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    source,
                    kind,
                    observation,
                    bearing,
                    1.0,
                    artifact_hash,
                    observed_at,
                    detail,
                    created_at,
                ),
            )
            linked_hypothesis = {
                1: "cors",
                2: "jwt",
                4: "cookie",
                6: "jwt",
            }.get(index)
            if linked_hypothesis:
                connection.execute(
                    """INSERT INTO hypothesis_evidence(session_id, hypothesis_id, evidence_id)
                       VALUES (?, ?, ?)""",
                    (session_id, linked_hypothesis, cursor.lastrowid),
                )
        connection.execute(
            """INSERT INTO history(session_id, event_type, summary, created_at)
               VALUES (?, 'session.created', 'Sessão demonstrativa inicializada', ?)""",
            (session_id, created_at),
        )


def active_session_id(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        "SELECT value FROM settings WHERE key = 'active_session_id'"
    ).fetchone()
    if not row:
        raise RuntimeError("WOLF database has not been initialized")
    return str(row["value"])


def record_history(
    connection: sqlite3.Connection,
    session_id: str,
    event_type: str,
    summary: str,
    payload_json: str = "{}",
) -> None:
    connection.execute(
        """INSERT INTO history(session_id, event_type, summary, payload_json, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (session_id, event_type, summary, payload_json, now_iso()),
    )