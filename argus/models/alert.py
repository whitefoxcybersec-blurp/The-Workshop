from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Detection:
    name: str
    severity: str
    score: int
    event_id: str
    timestamp: str
    src_ip: str | None
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "severity": self.severity,
            "score": self.score,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "src_ip": self.src_ip,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class Alert:
    alert_id: str
    event_id: str
    timestamp: str
    src_ip: str | None
    risk_score: int
    severity: str
    detections: list[Detection]
    event: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.alert_id,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "src_ip": self.src_ip,
            "risk_score": self.risk_score,
            "severity": self.severity,
            "detections": [detection.to_dict() for detection in self.detections],
            "event": self.event,
        }