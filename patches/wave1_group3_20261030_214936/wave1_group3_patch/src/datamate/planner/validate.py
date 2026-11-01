"""Fail-closed gates before handing the existing plan to the oracle executor."""

from __future__ import annotations

from dataclasses import fields
from datetime import date
from pathlib import Path
from typing import Any

from datamate.load_business import read_config
from datamate.planner.schema import (ANSWER_FOR_FAMILY, CAPABILITIES,
                                     OPERATION_FOR_FAMILY, QueryPlan, QuestionIntent)
from datamate.time.resolve import resolve_period


class PlannerFailure(ValueError):
    pass


SUPPORTED: dict[tuple[str, str], set[str]] = {
    ("train", "biz_129"): {"time", "revenue", "order_count", "cancel"},
    ("train", "biz_102"): {"revenue"},
    ("train", "biz_103"): {"revenue"},
    ("train", "biz_104"): {"revenue"},
    ("public_test", "dev_002"): {"order_count", "cancel", "cancel_count"},
}


def _exact_keys(raw: dict[str, Any], cls: type) -> None:
    if not isinstance(raw, dict) or set(raw) != {f.name for f in fields(cls)}:
        raise PlannerFailure(f"schema_keys:{cls.__name__}")


def validate_intent(raw: dict[str, Any], question: dict[str, Any], project_root: Path) -> QuestionIntent:
    _exact_keys(raw, QuestionIntent)
    if any(type(raw[k]) is not str or not raw[k] for k in
           ("question_id", "business_id", "ruleset", "as_of_date", "family", "metric", "answer_type", "period_expression")):
        raise PlannerFailure("schema_scalar")
    if any(raw[k] != question.get(qk) for k, qk in
           (("question_id", "id"), ("business_id", "business_id"), ("as_of_date", "as_of_date"))):
        raise PlannerFailure("question_identity_mismatch")
    identity = (raw["ruleset"], raw["business_id"])
    if identity not in SUPPORTED:
        raise PlannerFailure("unsupported_business_or_ruleset")
    family = raw["family"]
    if family not in OPERATION_FOR_FAMILY:
        raise PlannerFailure("unsupported_family")
    if family not in SUPPORTED[identity]:
        raise PlannerFailure("family_not_enabled_for_business")
    op = OPERATION_FOR_FAMILY[family]
    if raw["metric"] != op or raw["answer_type"] != ANSWER_FOR_FAMILY[family]:
        raise PlannerFailure("metric_or_answer_type_mismatch")
    if any(raw[k] is not None for k in ("entity_filter", "grouping", "comparison", "top_k")):
        raise PlannerFailure("unsupported_filter_group_comparison_or_top_k")
    for k in ("required_capabilities", "operations", "validation_checks", "ambiguities"):
        if not isinstance(raw[k], (tuple, list)) or any(type(x) is not str for x in raw[k]):
            raise PlannerFailure(f"schema_array:{k}")
    if tuple(raw["required_capabilities"]) != CAPABILITIES[family] or tuple(raw["operations"]) != (op,):
        raise PlannerFailure("capability_or_operation_mismatch")
    if tuple(raw["validation_checks"]) != ("identity", "capability", "period", "allowlist"):
        raise PlannerFailure("validation_checks_mismatch")
    if raw["ambiguities"]:
        raise PlannerFailure("unresolved_ambiguity")
    try:
        as_of = date.fromisoformat(raw["as_of_date"])
        config = read_config(raw["ruleset"], raw["business_id"], project_root / "configs/businesses")
        sources = config["sources"]
        if family == "revenue":
            if config.get("archetype") == "monthly_excel_sales_lines":
                monthly = config.get("monthly_sales", {})
                source = sources.get(monthly.get("source"), {})
                roles = source.get("semantic_columns", {})
                if monthly.get("revenue_enabled") is not True or not {
                    "order_id", "order_date", "status", "product_name", "line_amount"
                } <= roles.keys():
                    raise PlannerFailure("missing_monthly_revenue_capability")
            elif not {"orders", "order_lines"} <= sources.keys():
                raise PlannerFailure("missing_source_capability")
        if family in {"order_count", "cancel", "cancel_count"} and "orders" not in sources:
            raise PlannerFailure("missing_source_capability")
        calendar = project_root / raw["ruleset"] / "calendar.csv"
        if not calendar.is_file():
            raise PlannerFailure("missing_calendar")
        period = resolve_period(raw["period_expression"], as_of, calendar, raw["ruleset"])
        if period.start > as_of or period.end > as_of:
            raise PlannerFailure("future_period")
        coverage = config.get("monthly_sales") or config.get("order_header", {})
        if coverage:
            coverage_start = date.fromisoformat(coverage["data_start"])
            coverage_end = date.fromisoformat(coverage["data_end"])
            if period.end < coverage_start or period.start > coverage_end:
                raise PlannerFailure("period_outside_verified_data_range")
        if period.mode != "flow" and family != "time":
            raise PlannerFailure("unsupported_snapshot_metric")
    except PlannerFailure:
        raise
    except (ValueError, OSError, KeyError) as exc:
        raise PlannerFailure(f"invalid_period_or_config:{exc}") from exc
    return QuestionIntent(**{**raw, **{k: tuple(raw[k]) for k in
                            ("required_capabilities", "operations", "validation_checks", "ambiguities")}})


def to_query_plan(intent: QuestionIntent, question: dict[str, Any], project_root: Path) -> QueryPlan:
    validate_intent(intent.to_dict(), question, project_root)
    plan = QueryPlan(plan_id=question["id"], operation=intent.metric,
                     business_id=intent.business_id, ruleset=intent.ruleset,
                     period=intent.period_expression, as_of_date=intent.as_of_date)
    validate_query_plan(plan.to_dict(), question, project_root)
    return plan


def validate_query_plan(raw: dict[str, Any], question: dict[str, Any], project_root: Path) -> QueryPlan:
    _exact_keys(raw, QueryPlan)
    if any(type(v) is not str or not v for v in raw.values()):
        raise PlannerFailure("plan_schema_scalar")
    if raw["plan_id"] != question.get("id") or raw["business_id"] != question.get("business_id") or raw["as_of_date"] != question.get("as_of_date"):
        raise PlannerFailure("plan_question_identity_mismatch")
    if (raw["ruleset"], raw["business_id"]) not in SUPPORTED:
        raise PlannerFailure("plan_unsupported_business_or_ruleset")
    if raw["operation"] not in OPERATION_FOR_FAMILY.values():
        raise PlannerFailure("plan_operation_not_allowed")
    family = next(k for k, v in OPERATION_FOR_FAMILY.items() if v == raw["operation"])
    check = {"question_id": question["id"], "business_id": raw["business_id"],
             "ruleset": raw["ruleset"], "as_of_date": raw["as_of_date"],
             "family": family, "metric": raw["operation"], "answer_type": ANSWER_FOR_FAMILY[family],
             "period_expression": raw["period"], "entity_filter": None, "grouping": None,
             "comparison": None, "top_k": None, "required_capabilities": CAPABILITIES[family],
             "operations": (raw["operation"],),
             "validation_checks": ("identity", "capability", "period", "allowlist"), "ambiguities": ()}
    validate_intent(check, question, project_root)
    return QueryPlan(**raw)
