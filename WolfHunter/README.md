# WOLF

**Hunt uncertainty, not targets.**

WOLF is a local, passive-first investigation workspace for authorized security research. Its FastAPI Core serves the existing dashboard, persists sessions and evidence in SQLite, normalizes imported artifacts, and records policy boundary stops. All initial evidence is synthetic demo data.

## Run locally

Python 3.11 or newer is recommended. From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn wolf.main:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. The browser talks only to the local Core. SQLite is stored at `~/.local/share/wolf/wolf.sqlite3` by default; set `WOLF_DB_PATH` to choose another location. The app binds to loopback, not a network interface.

## Evidence

- Add a normalized observation from the Evidence Stream.
- Import `.json` evidence records, `.har` response headers, or saved `.headers`/`.txt` header blocks.
- Every observation records its source, type, bearing, confidence, SHA-256 artifact hash, observation time, and detail.
- Imports inspect security-relevant headers only. Cookie values and HAR query strings are not stored; cookie attributes are summarized as flags.
- Evidence, hypothesis links, sessions, scopes, and event history persist in SQLite.

The evidence API is available under `/api`; interactive OpenAPI documentation is at `/docs`. The implemented routes include session creation/read, evidence list/create/import, hypothesis list/detail, scope read/check, history, and health.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -v
```

## Current boundaries

The default `demo.test` scope is illustrative, stored with the session, and only supports a local hostname check. It is not a signed authorization document or a production policy engine. No Observer, recon executor, target requests, WebSocket, or external notifications exist yet. The Bayesian display remains a client-side demonstration; do not treat its score as a validated finding or use this MVP as authorization to test a target.