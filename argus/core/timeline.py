from typing import Any


def build_timeline(
    events: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    timeline = [{"kind": "event", **event} for event in events]
    timeline.extend({"kind": "alert", **alert} for alert in alerts)
    return sorted(timeline, key=lambda item: (item["timestamp"], item["kind"]))