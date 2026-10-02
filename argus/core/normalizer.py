from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Any
from uuid import uuid4

from argus.models.event import Event


_ALIASES = {
    "timestamp", "ts", "time", "@timestamp", "source", "host", "agent",
    "event", "event_type", "type", "src_ip", "source_ip", "src", "id.orig_h",
    "user", "username", "result", "status", "outcome", "id",
}


def _timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    else:
        raise ValueError("timestamp must be ISO-8601 text or a Unix timestamp")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _first(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        if record.get(name) is not None:
            return record[name]
    return None


def normalize_event(record: dict[str, Any]) -> Event:
    timestamp = _timestamp(_first(record, "timestamp", "@timestamp", "ts", "time"))
    source = str(_first(record, "source", "host", "agent") or "unknown").strip()
    event_type = str(_first(record, "event", "event_type", "type") or "unknown").strip()
    src_ip_value = _first(record, "src_ip", "source_ip", "src", "id.orig_h")
    src_ip = None
    if src_ip_value not in (None, ""):
        try:
            src_ip = str(ip_address(str(src_ip_value)))
        except ValueError as error:
            raise ValueError(f"invalid source IP address: {src_ip_value}") from error
    user_value = _first(record, "user", "username")
    result_value = _first(record, "result", "status", "outcome")
    fields = {key: value for key, value in record.items() if key not in _ALIASES}
    return Event(
        timestamp=timestamp,
        source=source or "unknown",
        event_type=event_type or "unknown",
        src_ip=src_ip,
        user=str(user_value) if user_value is not None else None,
        result=str(result_value).lower() if result_value is not None else None,
        fields=fields,
        event_id=str(record.get("id") or "") or uuid4().hex,
    )