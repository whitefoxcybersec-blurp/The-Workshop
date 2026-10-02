from collections.abc import Iterator
from pathlib import Path
from typing import Any

from argus.collectors.jsonl import JSONLCollector


class NetworkCollector:
    """Adapt Zeek conn.log JSON records to ARGUS's common event shape."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def records(self) -> Iterator[dict[str, Any]]:
        for record in JSONLCollector(self.path).records():
            fields = {
                "destination_ip": record.get("id.resp_h"),
                "destination_port": record.get("id.resp_p"),
                "service": record.get("service"),
                "protocol": record.get("proto"),
                "connection_state": record.get("conn_state"),
                "duration": record.get("duration"),
                "orig_bytes": record.get("orig_bytes"),
                "resp_bytes": record.get("resp_bytes"),
                "uid": record.get("uid"),
            }
            yield {
                "timestamp": record.get("ts"),
                "source": "network",
                "event": "network_connection",
                "src_ip": record.get("id.orig_h"),
                "result": record.get("conn_state"),
                **{key: value for key, value in fields.items() if value is not None},
            }