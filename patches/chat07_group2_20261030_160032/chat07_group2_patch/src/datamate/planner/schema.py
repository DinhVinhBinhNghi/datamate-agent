"""Typed intent and the existing Chat 4 oracle plan contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

Family = Literal["time", "revenue", "order_count", "cancel", "cancel_count"]
Operation = Literal["resolve_period", "revenue", "order_count", "cancel_rate", "cancel_count"]
AnswerType = Literal["date", "number", "percent"]

OPERATION_FOR_FAMILY: dict[str, str] = {
    "time": "resolve_period", "revenue": "revenue",
    "order_count": "order_count", "cancel": "cancel_rate", "cancel_count": "cancel_count",
}
ANSWER_FOR_FAMILY: dict[str, str] = {
    "time": "date", "revenue": "number", "order_count": "number",
    "cancel": "percent", "cancel_count": "number",
}
CAPABILITIES: dict[str, tuple[str, ...]] = {
    "time": ("train_calendar",),
    "revenue": ("orders", "order_lines", "revenue_rule"),
    "order_count": ("orders", "order_count_rule"),
    "cancel": ("orders", "cancel_rate_rule"),
    "cancel_count": ("orders", "cancel_count_rule"),
}


@dataclass(frozen=True)
class QuestionIntent:
    question_id: str
    business_id: str
    ruleset: Literal["train", "public_test"]
    as_of_date: str
    family: Family
    metric: Operation
    answer_type: AnswerType
    period_expression: str
    entity_filter: None
    grouping: None
    comparison: None
    top_k: None
    required_capabilities: tuple[str, ...]
    operations: tuple[Operation, ...]
    validation_checks: tuple[str, ...]
    ambiguities: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class QueryPlan:
    """Exact six fields consumed by Chat 4 execute_plan; no expected_value at runtime."""
    plan_id: str
    operation: Operation
    business_id: str
    ruleset: Literal["train", "public_test"]
    period: str
    as_of_date: str

    def to_dict(self) -> dict:
        return asdict(self)


def json_schema() -> dict:
    """Strict JSON Schema for external planner output; runtime validation is validate.py."""
    properties = {
        "question_id": {"type": "string", "minLength": 1},
        "business_id": {"enum": ["biz_129", "dev_002"]},
        "ruleset": {"enum": ["train", "public_test"]},
        "as_of_date": {"type": "string", "format": "date"},
        "family": {"enum": list(OPERATION_FOR_FAMILY)},
        "metric": {"enum": list(OPERATION_FOR_FAMILY.values())},
        "answer_type": {"enum": ["date", "number", "percent"]},
        "period_expression": {"type": "string", "minLength": 1},
        "entity_filter": {"type": "null"}, "grouping": {"type": "null"},
        "comparison": {"type": "null"}, "top_k": {"type": "null"},
        "required_capabilities": {"type": "array", "items": {"enum": sorted(set(sum(CAPABILITIES.values(), ())) )}, "uniqueItems": True},
        "operations": {"type": "array", "items": {"enum": list(OPERATION_FOR_FAMILY.values())}, "minItems": 1, "maxItems": 1},
        "validation_checks": {"type": "array", "items": {"enum": ["identity", "capability", "period", "allowlist"]}, "uniqueItems": True},
        "ambiguities": {"type": "array", "items": {"type": "string"}},
    }
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}
