import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from argus.collectors.syslog import parse_syslog_line
from argus.core.correlator import CorrelationEngine
from argus.core.normalizer import normalize_event
from argus.core.scoring import RiskScorer
from argus.detection.behavioral import BehavioralEngine
from argus.detection.rules import Rule, RuleEngine
from argus.models.event import Event
from argus.storage.database import Database


class NormalizerTests(unittest.TestCase):
    def test_normalizes_aliases_and_ip(self) -> None:
        event = normalize_event(
            {
                "timestamp": "2026-10-02T13:37:00Z",
                "host": "linux-a",
                "event_type": "authentication",
                "source_ip": "192.168.1.50",
                "username": "root",
                "status": "FAILED",
                "pid": 123,
            }
        )
        self.assertEqual(event.source, "linux-a")
        self.assertEqual(event.src_ip, "192.168.1.50")
        self.assertEqual(event.result, "failed")
        self.assertEqual(event.fields["pid"], 123)

    def test_rejects_invalid_source_ip(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid source IP"):
            normalize_event({"event": "authentication", "src_ip": "not-an-ip"})


class CorrelationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CorrelationEngine(
            RuleEngine([Rule("root_login", "authentication", {"user": "root", "result": "success"}, "high", 30)]),
            BehavioralEngine(failure_threshold=15, window_seconds=30),
            RiskScorer(window_seconds=300),
        )
        self.start = datetime(2026, 10, 2, 13, 36, tzinfo=timezone.utc)

    def event(self, index: int, result: str = "failed", source: str = "linux") -> Event:
        return Event(
            timestamp=self.start.replace(second=index),
            source=source,
            event_type="authentication" if source == "linux" else "network_connection",
            src_ip="192.168.1.50",
            user="root",
            result=result,
        )

    def test_one_failure_is_not_an_alert_then_threshold_and_success_raise_risk(self) -> None:
        for index in range(14):
            self.assertIsNone(self.engine.process(self.event(index)))

        brute_force = self.engine.process(self.event(14))
        self.assertIsNotNone(brute_force)
        self.assertEqual(brute_force.risk_score, 55)
        self.assertEqual(brute_force.severity, "high")
        self.assertEqual(brute_force.detections[0].name, "ssh_brute_force")

        successful_login = self.engine.process(self.event(15, result="success"))
        self.assertIsNotNone(successful_login)
        self.assertEqual(successful_login.risk_score, 100)
        self.assertEqual(
            {detection.name for detection in successful_login.detections},
            {"root_login", "successful_login_after_brute_force"},
        )

    def test_same_ip_in_another_source_adds_correlation(self) -> None:
        first = Event(self.start, "linux", "system_log", src_ip="192.168.1.50")
        second = Event(self.start.replace(second=1), "network", "network_connection", src_ip="192.168.1.50")
        self.assertIsNone(self.engine.process(first))
        alert = self.engine.process(second)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.detections[0].name, "ip_seen_across_sources")

    def test_expired_brute_force_window_can_alert_again(self) -> None:
        for index in range(15):
            self.engine.process(self.event(index))

        later_start = self.start + timedelta(seconds=60)
        for index in range(14):
            event = Event(
                timestamp=later_start + timedelta(seconds=index),
                source="linux",
                event_type="authentication",
                src_ip="192.168.1.50",
                result="failed",
            )
            self.assertIsNone(self.engine.process(event))

        final_event = Event(
            timestamp=later_start + timedelta(seconds=14),
            source="linux",
            event_type="authentication",
            src_ip="192.168.1.50",
            result="failed",
        )
        alert = self.engine.process(final_event)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.detections[0].name, "ssh_brute_force")


class CollectorAndStorageTests(unittest.TestCase):
    def test_syslog_auth_failure_is_normalized(self) -> None:
        parsed = parse_syslog_line(
            "Oct  2 13:36:01 host sshd[123]: Failed password for root from 192.168.1.50 port 22 ssh2",
            now=datetime(2026, 10, 2, tzinfo=timezone.utc),
        )
        event = normalize_event(parsed)
        self.assertEqual(event.event_type, "authentication")
        self.assertEqual(event.result, "failed")
        self.assertEqual(event.user, "root")
        self.assertEqual(event.src_ip, "192.168.1.50")

    def test_sqlite_persists_events_alerts_and_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Database(Path(temporary_directory) / "argus.db")
            event = normalize_event(
                {
                    "timestamp": "2026-10-02T13:37:00Z",
                    "source": "linux",
                    "event": "authentication",
                    "src_ip": "192.168.1.50",
                    "user": "root",
                    "result": "success",
                }
            )
            database.record_event(event)
            engine = CorrelationEngine(
                RuleEngine([Rule("root_login", "authentication", {"user": "root"}, "high", 30)]),
                BehavioralEngine(),
                RiskScorer(),
            )
            alert = engine.process(event)
            self.assertIsNotNone(alert)
            database.record_alert(alert)
            self.assertEqual(len(database.list_alerts()), 1)
            timeline = database.timeline("192.168.1.50")
            self.assertEqual({item["kind"] for item in timeline}, {"event", "alert"})


if __name__ == "__main__":
    unittest.main()