"""Small, intentionally narrow question templates with no answer lookup."""

from __future__ import annotations

import re
import unicodedata

from datamate.planner.schema import ANSWER_FOR_FAMILY, CAPABILITIES, OPERATION_FOR_FAMILY, QuestionIntent
from datamate.planner.direct_revenue import classify_direct_revenue
from datamate.planner.validate import PlannerFailure

_TEMPLATES = (
    ("time", re.compile(r"(.+?) là khoảng thời gian nào[.?!]?", re.I)),
    ("revenue", re.compile(r"(?:cho tôi biết |tổng )?doanh thu (.+?)(?: là bao nhiêu)?[.?!]?", re.I)),
    ("order_count", re.compile(r"(?:cho tôi biết )?số đơn (.+?)(?: là bao nhiêu)?[.?!]?", re.I)),
    ("cancel", re.compile(r"(?:trong )?(.+?)[, ]+tỉ lệ đơn huỷ là bao nhiêu phần trăm(?: nhỉ)?[.?!]?", re.I)),
)


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
    return " ".join("".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").split())


def _public_dev002_period(text: str) -> str | None:
    if re.search(r"\b(hom|bua)\s+(ni|nay)\b", text):
        return "hôm nay"
    if re.search(r"\b(hom|bua)\s+qua\b", text):
        return "hôm qua"
    quarter = re.search(r"\bquy\s*([1-4])\s*/\s*(20\d{2})\b", text)
    if quarter:
        return f"quý {quarter.group(1)}/{quarter.group(2)}"
    month = re.search(r"\bthang\s*(\d{1,2})\s+nam\s+(20\d{2})\b", text)
    if not month:
        month = re.search(r"\b(?:thang|th|t)\s*(\d{1,2})\s*/\s*(20\d{2})\b", text)
    if not month:
        short = re.search(r"(?<!\d)(\d{1,2})\s*/\s*(\d{2})(?!\d)", text)
        if short:
            return f"tháng {int(short.group(1))}/{2000 + int(short.group(2))}"
        return None
    return f"tháng {int(month.group(1))}/{int(month.group(2))}"


def _plan_public_dev002(question: dict) -> tuple[str, str]:
    text = _fold(" ".join(question["question"].strip().split()))
    period = _public_dev002_period(text)
    if period is None:
        raise PlannerFailure("unsupported_public_dev002_period")
    has_cancel = "huy" in text
    rate_words = "%" in text or "phan tram" in text or "ti le" in text or "chiem bao nhieu" in text
    if has_cancel and rate_words:
        return "cancel", period
    if has_cancel and re.search(r"(?:bao nhieu|bnhiu|may)\s+don|don\s+bi\s+huy|bi\s+huy\s+bao\s+nhieu\s+don", text):
        return "cancel_count", period
    if not has_cancel and re.search(r"(?:bao nhieu|bnhiu|may)\s+don|duoc\s+may\s+don|chot\s+duoc\s+may\s+don", text):
        return "order_count", period
    raise PlannerFailure("unsupported_public_dev002_question_template")


def plan_heuristic(question: dict) -> QuestionIntent:
    text = " ".join(question["question"].strip().split())
    if question.get("business_id") == "dev_002":
        family, period = _plan_public_dev002(question)
        op = OPERATION_FOR_FAMILY[family]
        return QuestionIntent(
            question_id=question["id"], business_id="dev_002", ruleset="public_test",
            as_of_date=question["as_of_date"], family=family, metric=op,
            answer_type=ANSWER_FOR_FAMILY[family], period_expression=period,
            entity_filter=None, grouping=None, comparison=None, top_k=None,
            required_capabilities=CAPABILITIES[family], operations=(op,),
            validation_checks=("identity", "capability", "period", "allowlist"), ambiguities=(),
        )
    if question.get("business_id") in {"biz_102", "biz_103", "biz_104"}:
        classification = classify_direct_revenue(text)
        if classification.category != "direct_revenue" or not classification.period_expression:
            raise PlannerFailure(
                "unsupported_monthly_sales_question:" + classification.category
            )
        family = "revenue"
        op = OPERATION_FOR_FAMILY[family]
        return QuestionIntent(
            question_id=question["id"], business_id=question["business_id"],
            ruleset="train", as_of_date=question["as_of_date"], family=family,
            metric=op, answer_type=ANSWER_FOR_FAMILY[family],
            period_expression=classification.period_expression,
            entity_filter=None, grouping=None, comparison=None, top_k=None,
            required_capabilities=CAPABILITIES[family], operations=(op,),
            validation_checks=("identity", "capability", "period", "allowlist"),
            ambiguities=(),
        )
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
