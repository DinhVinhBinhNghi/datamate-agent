"""Small, intentionally narrow question templates with no answer lookup."""

from __future__ import annotations

import re

from datamate.planner.schema import ANSWER_FOR_FAMILY, CAPABILITIES, OPERATION_FOR_FAMILY, QuestionIntent
from datamate.planner.validate import PlannerFailure

_TEMPLATES = (
    ("time", re.compile(r"(.+?) là khoảng thời gian nào[.?!]?", re.I)),
    ("revenue", re.compile(r"(?:cho tôi biết |tổng )?doanh thu (.+?)(?: là bao nhiêu)?[.?!]?", re.I)),
    ("order_count", re.compile(r"(?:cho tôi biết )?số đơn (.+?)(?: là bao nhiêu)?[.?!]?", re.I)),
    ("cancel", re.compile(r"(?:trong )?(.+?)[, ]+tỉ lệ đơn huỷ là bao nhiêu phần trăm(?: nhỉ)?[.?!]?", re.I)),
)


def plan_heuristic(question: dict) -> QuestionIntent:
    text = " ".join(question["question"].strip().split())
    matches = []
    for family, pattern in _TEMPLATES:
        match = pattern.fullmatch(text)
        if match:
            matches.append((family, match.group(1).strip()))
    if len(matches) != 1:
        raise PlannerFailure("unsupported_or_ambiguous_question_template")
    family, period = matches[0]
    op = OPERATION_FOR_FAMILY[family]
    return QuestionIntent(
        question_id=question["id"], business_id=question["business_id"],
        ruleset="train", as_of_date=question["as_of_date"],
        family=family, metric=op, answer_type=ANSWER_FOR_FAMILY[family],
        period_expression=period, entity_filter=None, grouping=None,
        comparison=None, top_k=None, required_capabilities=CAPABILITIES[family],
        operations=(op,), validation_checks=("identity", "capability", "period", "allowlist"),
        ambiguities=(),
    )
