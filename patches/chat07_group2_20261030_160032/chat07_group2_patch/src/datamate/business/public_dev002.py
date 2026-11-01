"""Verified public_test/dev_002 order and cancellation operations."""

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any

import pandas as pd

from datamate.business.status import is_cancelled, is_returned, order_count_eligible
from datamate.readers import load_source
from datamate.time.resolve import resolve_period


RULE_SOURCE = "public_test/rulebook.md §1; public_test/data/dev_002/README.md"
SUPPORTED_OPERATIONS = {"order_count", "cancel_count", "cancel_rate"}
_HEADER_CACHE: dict[tuple[Any, ...], tuple[pd.DataFrame, dict[str, Any]]] = {}


def collapse_order_headers(lines: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    source = config["sources"]["orders"]
    semantic = source["semantic_columns"]
    key = semantic["order_id"]
    date_col = semantic["order_date"]
    status_col = semantic["status"]
    pattern = config["order_header"]["order_id_pattern"]
    valid_key = lines[key].map(lambda value: isinstance(value, str) and re.fullmatch(pattern, value.strip()) is not None)
    data = lines.loc[valid_key].copy()
    structural_rows = int((~valid_key).sum())
    if data.empty:
        raise ValueError("No valid order rows remain after structural-row filtering")
    data[key] = data[key].str.strip()
    data["_normalized_order_date"] = pd.to_datetime(data[date_col], errors="coerce", dayfirst=True).dt.date
    if data["_normalized_order_date"].isna().any():
        raise ValueError("Order rows contain unparseable dates")
    if data[status_col].isna().any():
        raise ValueError("Order rows contain null statuses")
    data["_normalized_status"] = data[status_col].astype(str).str.strip().str.casefold()
    checks = data.groupby(key, sort=False).agg(
        date_values=("_normalized_order_date", "nunique"),
        status_values=("_normalized_status", "nunique"),
        source_files=("_source_file", "nunique"),
    )
    conflicts = checks[(checks["date_values"] != 1) | (checks["status_values"] != 1)]
    if not conflicts.empty:
        raise ValueError(f"Conflicting order headers for {len(conflicts)} order IDs")
    cross_file = checks[checks["source_files"] != 1]
    if not cross_file.empty:
        raise ValueError(f"Order IDs span multiple monthly fragments: {len(cross_file)}")
    headers = data.drop_duplicates(key, keep="first").copy()
    headers[date_col] = headers["_normalized_order_date"]
    evidence = {
        "raw_order_line_rows": int(len(lines)),
        "valid_order_line_rows": int(len(data)),
        "structural_rows_excluded": structural_rows,
        "order_headers_after_collapse": int(len(headers)),
        "fragment_count": int(data["_source_file"].nunique()),
        "provenance_sources": sorted(set(data["_source_file"].astype(str))),
    }
    return headers, evidence


def _cached_headers(config: dict[str, Any], data_root: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    root = Path(data_root).resolve()
    pattern = config["sources"]["orders"].get("path_glob", "")
    signature = tuple(
        (str(path.resolve()), path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(root.glob(pattern)) if path.is_file()
    )
    key = (str(root), json.dumps(config, ensure_ascii=False, sort_keys=True), signature)
    if key not in _HEADER_CACHE:
        lines = load_source(config, "orders", root)
        _HEADER_CACHE[key] = collapse_order_headers(lines, config)
    headers, evidence = _HEADER_CACHE[key]
    return headers.copy(), {**evidence, "provenance_sources": list(evidence["provenance_sources"])}


def calculate_dev002(
    config: dict[str, Any], data_root: str | Path, period_expression: str,
    as_of_date: str, operation: str,
) -> dict[str, Any]:
    if (config.get("split"), config.get("business_id")) != ("public_test", "dev_002"):
        raise ValueError("Public dev_002 operation received the wrong business config")
    if operation not in SUPPORTED_OPERATIONS:
        raise ValueError(f"Unsupported public dev_002 operation: {operation}")
    headers, load_evidence = _cached_headers(config, data_root)
    semantic = config["sources"]["orders"]["semantic_columns"]
    key, date_col, status_col = semantic["order_id"], semantic["order_date"], semantic["status"]
    period = resolve_period(period_expression, as_of_date, None, "public_test")
    in_period = headers[date_col].map(lambda value: period.start <= value <= period.end)
    period_orders = headers.loc[in_period]
    eligible = period_orders[status_col].map(lambda value: order_count_eligible(value, "public_test"))
    cancelled = period_orders[status_col].map(lambda value: is_cancelled(value, "public_test"))
    returned = period_orders[status_col].map(lambda value: is_returned(value, "public_test"))
    denominator = int(len(period_orders))
    eligible_count = int(eligible.sum())
    cancelled_count = int(cancelled.sum())
    rate = round(cancelled_count * 100 / denominator, 2) if denominator else None
    if operation == "order_count":
        answer_type, value = "number", eligible_count
    elif operation == "cancel_count":
        answer_type, value = "number", cancelled_count
    else:
        answer_type, value = ("unanswerable", None) if rate is None else ("percent", rate)
    evidence = {
        "business_id": "dev_002",
        "ruleset": "public_test",
        "rule_source": RULE_SOURCE,
        "period": {"start": period.start.isoformat(), "end": period.end.isoformat(), "inclusive": True},
        "grain": "one row per order after verified collapse from product lines",
        "count_key": key,
        "orders_total": int(len(headers)),
        "orders_in_period_all_statuses": denominator,
        "eligible_orders": eligible_count,
        "cancelled_orders": cancelled_count,
        "returned_orders_not_counted_as_cancelled": int(returned.sum()),
        "cancel_rate_percent": rate,
        "rounding": "2 decimal places",
        "null_order_keys": 0,
        "duplicate_order_keys": 0,
        "unsupported_reason": "denominator is zero" if operation == "cancel_rate" and denominator == 0 else None,
        **load_evidence,
    }
    return {"type": answer_type, "value": value, "evidence": evidence}
