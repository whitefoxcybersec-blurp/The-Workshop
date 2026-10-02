from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Event:
    timestamp: datetime
    source: str
    event_type: str
    src_ip: str | None = None
    user: str | None = None
    result: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.fields)
        payload.update(
            {
                "id": self.event_id,
                "timestamp": self.timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "source": self.source,
                "event": self.event_type,
                "src_ip": self.src_ip,
                "user": self.user,
                "result": self.result,
            }
        )
        return payload

    def value(self, name: str) -> Any:
        if name == "event":
            name = "event_type"
        if name in {"timestamp", "source", "event_type", "src_ip", "user", "result"}:
            return getattr(self, name)
        return self.fields.get(name)