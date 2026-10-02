from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from argus.models.alert import Detection
from argus.models.event import Event


@dataclass(frozen=True, slots=True)
class Rule:
    name: str
    event: str
    conditions: dict[str, Any]
    severity: str
    score: int


class RuleEngine:
    def __init__(self, rules: list[Rule]) -> None:
        self.rules = rules

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RuleEngine":
        with Path(path).open("r", encoding="utf-8") as input_file:
            configuration = yaml.safe_load(input_file) or {}
        definitions = configuration.get("rules", [])
        if not isinstance(definitions, list):
            raise ValueError("rules configuration must contain a list named 'rules'")
        rules = []
        for definition in definitions:
            if not isinstance(definition, dict):
                raise ValueError("each rule must be a mapping")
            try:
                rule = Rule(
                    name=str(definition["name"]),
                    event=str(definition["event"]),
                    conditions=dict(definition.get("conditions", {})),
                    severity=str(definition.get("severity", "medium")).lower(),
                    score=int(definition.get("score", 10)),
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"invalid rule definition: {definition!r}") from error
            if not 0 <= rule.score <= 100:
                raise ValueError(f"rule score must be between 0 and 100: {rule.name}")
            if rule.severity not in {"low", "medium", "high", "critical"}:
                raise ValueError(f"invalid severity in rule: {rule.name}")
            rules.append(rule)
        return cls(rules)

    def evaluate(self, event: Event) -> list[Detection]:
        matches = []
        for rule in self.rules:
            if event.event_type != rule.event:
                continue
            if any(event.value(field) != expected for field, expected in rule.conditions.items()):
                continue
            matches.append(
                Detection(
                    name=rule.name,
                    severity=rule.severity,
                    score=rule.score,
                    event_id=event.event_id,
                    timestamp=event.to_dict()["timestamp"],
                    src_ip=event.src_ip,
                    details={"matched_conditions": rule.conditions},
                )
            )
        return matches