import json
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from argus.storage.database import Database


class _APIHandler(BaseHTTPRequestHandler):
    def __init__(self, *args: Any, database: Database, **kwargs: Any) -> None:
        self.database = database
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        request = urlsplit(self.path)
        query = parse_qs(request.query)
        if request.path == "/health":
            self._send_json(200, {"status": "ok"})
        elif request.path == "/alerts":
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError:
                self._send_json(400, {"error": "limit must be an integer"})
                return
            self._send_json(200, {"alerts": self.database.list_alerts(limit)})
        elif request.path == "/timeline":
            try:
                limit = int(query.get("limit", ["500"])[0])
            except ValueError:
                self._send_json(400, {"error": "limit must be an integer"})
                return
            src_ip = query.get("src_ip", [None])[0]
            self._send_json(200, {"timeline": self.database.timeline(src_ip, limit)})
        else:
            self._send_json(404, {"error": "not found"})

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

def serve(database: Database, host: str = "127.0.0.1", port: int = 8765) -> None:
    handler = partial(_APIHandler, database=database)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"ARGUS API listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()