import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


class JSONLCollector:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def records(self) -> Iterator[dict[str, Any]]:
        with self.path.open("r", encoding="utf-8") as input_file:
            for line_number, line in enumerate(input_file, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"{self.path}:{line_number}: invalid JSON: {error.msg}") from error
                if not isinstance(record, dict):
                    raise ValueError(f"{self.path}:{line_number}: each JSONL record must be an object")
                yield record