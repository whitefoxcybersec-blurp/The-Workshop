from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from wolf.main import app


class WolfApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_db_path = os.environ.get("WOLF_DB_PATH")
        os.environ["WOLF_DB_PATH"] = str(Path(self.temp_dir.name) / "test.sqlite3")
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        if self.previous_db_path is None:
            os.environ.pop("WOLF_DB_PATH", None)
        else:
            os.environ["WOLF_DB_PATH"] = self.previous_db_path
        self.temp_dir.cleanup()

    def test_demo_session_and_linked_hypotheses_are_persisted(self) -> None:
        session = self.client.get("/api/session").json()
        counts = {
            item["id"]: item["evidence_count"]
            for item in self.client.get("/api/hypotheses").json()
        }

        self.assertEqual(session["evidence_count"], 8)
        self.assertEqual(counts, {"cookie": 1, "cors": 1, "jwt": 2})

    def test_evidence_create_updates_evidence_and_history(self) -> None:
        response = self.client.post(
            "/api/evidence",
            json={
                "source": "unit test",
                "kind": "HTTP",
                "observation": "Access-Control-Allow-Origin: https://example.invalid",
                "bearing": "supports",
                "detail": "saved response header",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()["artifact_hash"]), 64)
        self.assertEqual(self.client.get("/api/evidence").json()[0]["source"], "unit test")
        self.assertEqual(self.client.get("/api/hypotheses/cors").json()["evidence_count"], 2)
        self.assertIn("evidence.created", [item["event_type"] for item in self.client.get("/api/history").json()])

    def test_har_import_extracts_security_headers_and_redacts_cookie_values(self) -> None:
        artifact = {
            "log": {
                "entries": [
                    {
                        "request": {"url": "https://shop.demo.test/profile?token=private"},
                        "response": {
                            "status": 200,
                            "headers": [
                                {"name": "Access-Control-Allow-Origin", "value": "*"},
                                {"name": "Set-Cookie", "value": "sid=private; Secure"},
                            ],
                        },
                    }
                ]
            }
        }
        response = self.client.post(
            "/api/evidence/import",
            json={"format": "har", "source": "capture.har", "content": json.dumps(artifact)},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["imported"], 2)
        self.assertNotIn("sid=private", response.text)
        self.assertNotIn("token=private", response.text)

    def test_scope_policy_accepts_only_valid_hosts_under_configured_root(self) -> None:
        allowed = self.client.post("/api/scope/check", json={"host": "shop.demo.test"}).json()
        blocked = self.client.post("/api/scope/check", json={"host": "demo.test.attacker.invalid"}).json()
        malformed = self.client.post("/api/scope/check", json={"host": "shop..demo.test"}).json()

        self.assertTrue(allowed["allowed"])
        self.assertFalse(blocked["allowed"])
        self.assertFalse(malformed["allowed"])
        self.assertFalse(allowed["network_requested"])
        self.assertIn("policy.boundary_stop", [item["event_type"] for item in self.client.get("/api/history").json()])

    def test_new_session_starts_empty_and_becomes_active(self) -> None:
        response = self.client.post("/api/session", json={"name": "Isolated review"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.get("/api/session").json()["name"], "Isolated review")
        self.assertEqual(self.client.get("/api/evidence").json(), [])


if __name__ == "__main__":
    unittest.main()