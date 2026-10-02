import re
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SYSLOG_PREFIX = re.compile(
    r"^(?:<\d+>)?(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+"
    r"(?P<clock>\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<message>.*)$"
)
_SOURCE_IP = re.compile(r"\bfrom\s+([0-9a-fA-F:.]+)")
_USER = re.compile(r"\bfor\s+(?:invalid user\s+)?([^\s]+)")
_PAM_USER = re.compile(r"\buser=([^\s]+)")


def parse_syslog_line(line: str, now: datetime | None = None) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    match = _SYSLOG_PREFIX.match(line.strip())
    if match:
        timestamp = datetime.strptime(
            f"{current_time.year} {match['month']} {match['day']} {match['clock']}",
            "%Y %b %d %H:%M:%S",
        ).replace(tzinfo=timezone.utc)
        message = match["message"]
        host = match["host"]
    else:
        timestamp = current_time
        message = line.strip()
        host = "linux"

    lowered = message.lower()
    is_authentication = any(
        marker in lowered
        for marker in ("sshd", "pam_unix", "authentication", "password for")
    )
    result = None
    if any(marker in lowered for marker in ("failed", "failure", "authentication error")):
        result = "failed"
    elif any(marker in lowered for marker in ("accepted", "session opened", "authentication success")):
        result = "success"

    source_match = _SOURCE_IP.search(message)
    user_match = _USER.search(message) or _PAM_USER.search(message)
    return {
        "timestamp": timestamp.isoformat(),
        "source": host,
        "event": "authentication" if is_authentication else "system_log",
        "src_ip": source_match.group(1) if source_match else None,
        "user": user_match.group(1).rstrip(":") if user_match else None,
        "result": result,
        "message": message,
    }


class SyslogCollector:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def records(self) -> Iterator[dict[str, Any]]:
        with self.path.open("r", encoding="utf-8", errors="replace") as input_file:
            for line in input_file:
                if line.strip():
                    yield parse_syslog_line(line)