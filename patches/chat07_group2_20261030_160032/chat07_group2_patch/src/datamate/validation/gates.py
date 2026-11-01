from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from datamate.planner.schema import OPERATION_FOR_FAMILY


class GateFailure(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


SUPPORTED = {
    ("train", "biz_129"): {"revenue", "order_count", "cancel_rate"},
    ("public_test", "dev_002"): {"order_count", "cancel_count", "cancel_rate"},
}


def require_evidence(question: dict, plan: dict, answer: dict, root: Path) -> dict:
    if plan.get("plan_id") != question.get("id") or plan.get("business_id") != question.get("business_id"):
        raise GateFailure("identity_mismatch")
    identity = (plan.get("ruleset"), plan.get("business_id"))
    if identity not in SUPPORTED:
        raise GateFailure("unsupported_business_or_ruleset")
    operation = plan.get("operation")
    if operation not in SUPPORTED[identity] or operation not in OPERATION_FOR_FAMILY.values():
        raise GateFailure("unsupported_operation")
    evidence = answer.get("evidence")
    if not isinstance(evidence, dict):
        raise GateFailure("missing_evidence")
    if evidence.get("business_id") != plan["business_id"] or evidence.get("ruleset") != plan["ruleset"]:
        raise GateFailure("evidence_identity_mismatch")
    if not evidence.get("rule_source"):
        raise GateFailure("missing_rule_source")
    period = evidence.get("period")
    if not isinstance(period, dict) or period.get("inclusive") is not True:
        raise GateFailure("missing_period_evidence")
    try:
        start, end = date.fromisoformat(period["start"]), date.fromisoformat(period["end"])
        as_of = date.fromisoformat(plan["as_of_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GateFailure("invalid_period_evidence") from exc
    if start > end or end > as_of:
        raise GateFailure("period_out_of_bounds")
    ruleset = plan["ruleset"]
    if not (root / ruleset / "calendar.csv").is_file():
        raise GateFailure("missing_calendar")
    from datamate.time.resolve import resolve_period

    expected = resolve_period(plan["period"], as_of, root / ruleset / "calendar.csv", ruleset)
    if (start, end) != (expected.start, expected.end):
        raise GateFailure("period_mismatch")

    sources = evidence.get("provenance_sources")
    if sources is None:
        sources = [evidence["source"]] if evidence.get("source") else []
    needed = 2 if operation == "revenue" else 1
    if not isinstance(sources, list) or len(sources) < needed or any(not isinstance(s, str) or not s for s in sources):
        raise GateFailure("missing_source_provenance")
    data_root = (root / ruleset / "data" / plan["business_id"]).resolve()
    for source in sources:
        path = Path(source)
        resolved = (path if path.is_absolute() else root / path).resolve()
        if not resolved.is_relative_to(data_root) or not resolved.is_file():
            raise GateFailure("invalid_source_provenance")

    def nonnegative(name: str) -> int:
        value = evidence.get(name)
        if type(value) is not int or value < 0:
            raise GateFailure("invalid_evidence_count:" + name)
        return value

    if operation == "revenue":
        headers = nonnegative("order_headers")
        details = nonnegative("detail_rows_before_filter")
        matched = nonnegative("matched_detail_rows")
        unmatched = nonnegative("unmatched_detail_rows")
        eligible = nonnegative("eligible_detail_rows")
        period_rows = nonnegative("detail_rows_in_period")
        if not headers or not details or matched != details or unmatched or eligible > period_rows or period_rows > details:
            raise GateFailure("join_or_coverage_failure")
    else:
        total = nonnegative("orders_total") if operation == "order_count" or identity == ("public_test", "dev_002") else None
        period_count = nonnegative("orders_in_period_all_statuses")
        if operation == "order_count" and (not total or period_count > total or nonnegative("eligible_orders") > period_count):
            raise GateFailure("order_coverage_failure")
        if operation in {"cancel_count", "cancel_rate"} and (
            nonnegative("cancelled_orders") > period_count
            or (identity == ("public_test", "dev_002") and (not total or period_count > total))
        ):
            raise GateFailure("cancel_coverage_failure")
        if nonnegative("null_order_keys") or nonnegative("duplicate_order_keys"):
            raise GateFailure("invalid_order_keys")

    expected_type = {
        "revenue": "number", "order_count": "number",
        "cancel_count": "number", "cancel_rate": "percent",
    }[operation]
    if answer.get("type") not in {expected_type, "unanswerable"}:
        raise GateFailure("result_type_mismatch")
    if answer.get("type") == "unanswerable":
        if operation != "cancel_rate" or evidence.get("orders_in_period_all_statuses") != 0 or evidence.get("unsupported_reason") != "denominator is zero" or answer.get("value") is not None:
            raise GateFailure("unanswerable_without_proof")
    elif operation == "cancel_rate":
        if evidence["orders_in_period_all_statuses"] == 0 or answer.get("type") != "percent" or answer.get("value") != evidence.get("cancel_rate_percent"):
            raise GateFailure("cancel_result_mismatch")
    elif operation == "order_count" and answer.get("value") != evidence["eligible_orders"]:
        raise GateFailure("order_count_result_mismatch")
    elif operation == "cancel_count" and answer.get("value") != evidence["cancelled_orders"]:
        raise GateFailure("cancel_count_result_mismatch")
    return {"sources": sources, "period": period, "rule_source": evidence["rule_source"]}
