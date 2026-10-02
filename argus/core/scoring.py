from collections import defaultdict
from datetime import datetime, timedelta

from argus.models.alert import Detection


class RiskScorer:
    def __init__(self, window_seconds: int = 300) -> None:
        if window_seconds < 1:
            raise ValueError("risk window must be positive")
        self.window = timedelta(seconds=window_seconds)
        self._scores: dict[str, list[tuple[datetime, int]]] = defaultdict(list)

    def score(self, src_ip: str | None, timestamp: datetime, detections: list[Detection]) -> int:
        points = sum(detection.score for detection in detections)
        if src_ip is None:
            return min(points, 100)
        cutoff = timestamp - self.window
        history = self._scores[src_ip]
        history[:] = [
            (seen_at, score)
            for seen_at, score in history
            if cutoff <= seen_at <= timestamp
        ]
        if points:
            history.append((timestamp, points))
        return min(sum(score for _, score in history), 100)

    @staticmethod
    def severity(score: int) -> str:
        if score >= 80:
            return "critical"
        if score >= 50:
            return "high"
        if score >= 25:
            return "medium"
        return "low"