from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from wolf.database import (
    DEFAULT_HYPOTHESES,
    active_session_id,
    database_connection,
    initialize_database,
    now_iso,
    record_history,
)
from wolf.evidence import parse_artifact
from wolf.schemas import EvidenceCreate, EvidenceImport, ScopeCheck, SessionCreate


ROOT = Path(__file__).resolve().parent.parent
FRONTEND_FILES = {"index.html", "styles.css", "app.js"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="WOLF Core", version="0.2.0", lifespan=lifespan)


def current_session(connection: sqlite3.Connection) -> sqlite3.Row:
    session_id = active_session_id(connection)
    row = connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Active session not found")
    return row


def serialize_evidence(row: sqlite3.Row) -> dict[str, object]:
    observed_at = str(row["observed_at"])
    try:
        parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        time_label = parsed.astimezone(timezone.utc).strftime("%H:%M:%S")
    except ValueError:
        time_label = observed_at
    return {
        "id": f"EV-{int(row['id']):05d}",
        "source": row["source"],
        "kind": row["kind"],
        "title": row["observation"],
        "observation": row["observation"],
        "bearing": row["bearing"],
        "confidence": row["confidence"],
        "artifact_hash": row["artifact_hash"],
        "observed_at": observed_at,
        "detail": row["detail"],
        "time": time_label,
    }


def insert_evidence(
    connection: sqlite3.Connection,
    session_id: str,
    evidence: dict[str, object],
    observed_at: str | None = None,
) -> dict[str, object]:
    created_at = now_iso()
    observation = str(evidence["observation"]).strip()
    source = str(evidence["source"]).strip()
    kind = str(evidence["kind"])
    bearing = str(evidence["bearing"])
    confidence = float(evidence.get("confidence", 0.9))
    artifact_hash = str(evidence.get("artifact_hash") or hashlib.sha256(observation.encode()).hexdigest())
    detail = str(evidence.get("detail", ""))
    timestamp = observed_at or str(evidence.get("observed_at") or created_at)
    cursor = connection.execute(
        """INSERT INTO evidence
           (session_id, source, kind, observation, bearing, confidence,
            artifact_hash, observed_at, detail, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, source, kind, observation, bearing, confidence, artifact_hash, timestamp, detail, created_at),
    )
    record_history(
        connection,
        session_id,
        "evidence.created",
        f"Evidência registrada: {observation[:160]}",
        json.dumps({"evidence_id": cursor.lastrowid, "kind": kind, "artifact_hash": artifact_hash}),
    )
    evidence_text = f"{observation} {detail}".lower()
    linked_hypotheses = []
    if any(term in evidence_text for term in ("cors", "access-control", "origin")):
        linked_hypotheses.append("cors")
    if any(term in evidence_text for term in ("cookie", "samesite", "csrf")):
        linked_hypotheses.append("cookie")
    if any(term in evidence_text for term in ("jwt", "jwks", "token")):
        linked_hypotheses.append("jwt")
    for hypothesis_id in linked_hypotheses:
        connection.execute(
            """INSERT OR IGNORE INTO hypothesis_evidence(session_id, hypothesis_id, evidence_id)
               VALUES (?, ?, ?)""",
            (session_id, hypothesis_id, cursor.lastrowid),
        )
    row = connection.execute("SELECT * FROM evidence WHERE id = ?", (cursor.lastrowid,)).fetchone()
    assert row is not None
    return serialize_evidence(row)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "wolf-core"}


@app.get("/api/session")
def get_session() -> dict[str, object]:
    with database_connection() as connection:
        row = current_session(connection)
        count = connection.execute(
            "SELECT COUNT(*) AS total FROM evidence WHERE session_id = ?", (row["id"],)
        ).fetchone()["total"]
        return {"id": row["id"], "name": row["name"], "created_at": row["created_at"], "evidence_count": count}


@app.post("/api/session", status_code=201)
def create_session(payload: SessionCreate) -> dict[str, object]:
    session_id = str(uuid.uuid4())
    created_at = now_iso()
    with database_connection() as connection:
        connection.execute(
            "INSERT INTO sessions(id, name, created_at) VALUES (?, ?, ?)",
            (session_id, payload.name.strip(), created_at),
        )
        connection.execute(
            "UPDATE settings SET value = ? WHERE key = 'active_session_id'", (session_id,)
        )
        connection.execute(
            "INSERT INTO scopes(session_id, root, enabled, created_at) VALUES (?, 'demo.test', 1, ?)",
            (session_id, created_at),
        )
        for item in DEFAULT_HYPOTHESES:
            hypothesis_id, name, class_name, prior, threshold = item
            connection.execute(
                """INSERT INTO hypotheses
                   (id, session_id, name, class_name, prior, report_threshold, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (hypothesis_id, session_id, name, class_name, prior, threshold, created_at),
            )
        record_history(connection, session_id, "session.created", f"Sessão criada: {payload.name.strip()}")
    return {"id": session_id, "name": payload.name.strip(), "created_at": created_at, "evidence_count": 0}


@app.get("/api/evidence")
def list_evidence(session_id: str | None = Query(default=None)) -> list[dict[str, object]]:
    with database_connection() as connection:
        selected_session = session_id or active_session_id(connection)
        rows = connection.execute(
            "SELECT * FROM evidence WHERE session_id = ? ORDER BY observed_at DESC, id DESC",
            (selected_session,),
        ).fetchall()
        return [serialize_evidence(row) for row in rows]


@app.post("/api/evidence", status_code=201)
def create_evidence(payload: EvidenceCreate) -> dict[str, object]:
    with database_connection() as connection:
        session_id = active_session_id(connection)
        return insert_evidence(connection, session_id, payload.model_dump())


@app.post("/api/evidence/import", status_code=201)
def import_evidence(payload: EvidenceImport) -> dict[str, object]:
    try:
        normalized = parse_artifact(payload.format, payload.content, payload.source)
    except (ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=422, detail=f"Artifact could not be parsed: {error}") from error
    if not normalized:
        raise HTTPException(status_code=422, detail="No supported observations found in artifact")
    with database_connection() as connection:
        session_id = active_session_id(connection)
        created = [insert_evidence(connection, session_id, item) for item in normalized]
        record_history(
            connection,
            session_id,
            "artifact.imported",
            f"Artefato {payload.source} importado: {len(created)} observações",
            json.dumps({"format": payload.format, "count": len(created)}),
        )
    return {"imported": len(created), "evidence": created}


@app.get("/api/hypotheses")
def list_hypotheses() -> list[dict[str, object]]:
    with database_connection() as connection:
        session_id = active_session_id(connection)
        rows = connection.execute(
                """SELECT h.*, COUNT(he.evidence_id) AS evidence_count
               FROM hypotheses h
                    LEFT JOIN hypothesis_evidence he
                      ON he.session_id = h.session_id AND he.hypothesis_id = h.id
               WHERE h.session_id = ?
               GROUP BY h.session_id, h.id ORDER BY h.id""",
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]


@app.get("/api/hypotheses/{hypothesis_id}")
def get_hypothesis(hypothesis_id: str) -> dict[str, object]:
    with database_connection() as connection:
        session_id = active_session_id(connection)
        row = connection.execute(
                """SELECT h.*, COUNT(he.evidence_id) AS evidence_count
                    FROM hypotheses h LEFT JOIN hypothesis_evidence he
                      ON he.session_id = h.session_id AND he.hypothesis_id = h.id
               WHERE h.session_id = ? AND h.id = ? GROUP BY h.session_id, h.id""",
            (session_id, hypothesis_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Hypothesis not found")
        result = dict(row)
        result["evidence"] = [
            serialize_evidence(item)
            for item in connection.execute(
                """SELECT e.* FROM evidence e
                   JOIN hypothesis_evidence he ON he.evidence_id = e.id
                   WHERE he.session_id = ? AND he.hypothesis_id = ?
                   ORDER BY e.observed_at DESC""",
                (session_id, hypothesis_id),
            ).fetchall()
        ]
        return result


@app.get("/api/scope")
def get_scope() -> dict[str, object]:
    with database_connection() as connection:
        session_id = active_session_id(connection)
        rows = connection.execute(
            "SELECT root, enabled FROM scopes WHERE session_id = ? ORDER BY root", (session_id,)
        ).fetchall()
        return {"roots": [row["root"] for row in rows if row["enabled"]], "active_probes": False}


@app.post("/api/scope/check")
def check_scope(payload: ScopeCheck) -> dict[str, object]:
    host = payload.host.strip().lower().rstrip(".")
    valid_host = re.fullmatch(
        r"(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*",
        host,
    ) is not None
    with database_connection() as connection:
        session_id = active_session_id(connection)
        roots = [
            row["root"]
            for row in connection.execute(
                "SELECT root FROM scopes WHERE session_id = ? AND enabled = 1", (session_id,)
            ).fetchall()
        ]
        matched_root = next(
            (root for root in roots if valid_host and (host == root or host.endswith(f".{root}"))),
            None,
        )
        allowed = matched_root is not None
        if not allowed:
            record_history(
                connection,
                session_id,
                "policy.boundary_stop",
                f"Boundary stop: {host or 'host vazio'} fora do escopo",
                json.dumps({"host": host, "roots": roots}),
            )
        return {
            "host": host,
            "allowed": allowed,
            "matched_root": matched_root,
            "reason": "in_scope" if allowed else "outside_scope_or_invalid_host",
            "network_requested": False,
        }


@app.get("/api/history")
def list_history(limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, object]]:
    with database_connection() as connection:
        session_id = active_session_id(connection)
        rows = connection.execute(
            "SELECT * FROM history WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


@app.get("/", include_in_schema=False)
def frontend_index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/{asset_name}", include_in_schema=False)
def frontend_asset(asset_name: str) -> FileResponse:
    if asset_name not in FRONTEND_FILES - {"index.html"}:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(ROOT / asset_name)