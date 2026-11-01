"""Generic direct revenue for verified monthly Excel sales-line sources."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

from datamate.business.status import revenue_eligible
from datamate.readers import load_source
from datamate.time.resolve import Period


class MonthlySalesRevenueError(ValueError):
    """The configured monthly sales source failed a revenue safety invariant."""


_LINE_CACHE: dict[tuple[Any, ...], tuple[pd.DataFrame, dict[str, Any]]] = {}


def parse_vnd(value: Any) -> int | None:
    """Parse observed integer VND displays without binary floating-point sums."""
    if value is None or isinstance(value, bool) or pd.isna(value):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            amount = Decimal(str(value))
        except InvalidOperation:
            return None
        return int(amount) if amount == amount.to_integral_value() else None
    text = str(value).strip().lower()
    for token in ("vnd", "vnđ", "đ", "₫"):
        text = text.replace(token, "")
    text = text.replace(" ", "")
    sign = ""
    if text.startswith(("+", "-")):
        sign, text = text[0], text[1:]
    multiplier = Decimal(1)
    if text.endswith("k"):
        multiplier = Decimal(1000)
        text = text[:-1].replace(",", ".")
    elif text.endswith("tr"):
        multiplier = Decimal(1_000_000)
        text = text[:-2].replace(",", ".")
    else:
        separators = [separator for separator in (",", ".") if separator in text]
        if separators:
            groups = re.split(r"[,.]", text)
            if not (
                all(group.isdigit() for group in groups)
                and len(groups[0]) >= 1
                and all(len(group) == 3 for group in groups[1:])
            ):
                return None
            text = "".join(groups)
    try:
        amount = Decimal(sign + text) * multiplier
    except InvalidOperation:
        return None
    return int(amount) if amount == amount.to_integral_value() else None


def _source_signature(root: Path, source: dict[str, Any]) -> tuple[tuple[str, int, int], ...]:
    if isinstance(source.get("path"), str):
        paths = [root / source["path"]]
    elif isinstance(source.get("path_glob"), str):
        paths = sorted(path for path in root.glob(source["path_glob"]) if path.is_file())
    else:
        raise MonthlySalesRevenueError("Monthly sales source has no path or path_glob")
    if not paths or any(not path.is_file() for path in paths):
        raise MonthlySalesRevenueError("Monthly sales source files are missing")
    return tuple(
        (str(path.resolve()), path.stat().st_size, path.stat().st_mtime_ns)
        for path in paths
    )


def _prepare_lines(
    config: dict[str, Any], data_root: str | Path
) -> tuple[pd.DataFrame, dict[str, Any]]:
    monthly = config["monthly_sales"]
    source_name = monthly["source"]
    source = config["sources"][source_name]
    semantic = source["semantic_columns"]
    required = {"order_id", "order_date", "status", "product_name", "line_amount"}
    missing = sorted(required - set(semantic))
    if missing:
        raise MonthlySalesRevenueError(f"Missing monthly sales semantic roles: {missing}")
    root = Path(data_root).resolve()
    cache_key = (
        str(root),
        json.dumps(config, ensure_ascii=False, sort_keys=True),
        _source_signature(root, source),
    )
    if cache_key in _LINE_CACHE:
        frame, evidence = _LINE_CACHE[cache_key]
        return frame.copy(), json.loads(json.dumps(evidence, ensure_ascii=False))

    raw = load_source(config, source_name, root)
    order_col = semantic["order_id"]
    date_col = semantic["order_date"]
    status_col = semantic["status"]
    product_col = semantic["product_name"]
    amount_col = semantic["line_amount"]
    try:
        order_pattern = re.compile(monthly["order_id_pattern"])
    except (KeyError, re.error) as exc:
        raise MonthlySalesRevenueError(f"Invalid order_id_pattern: {exc}") from exc
    valid_order = raw[order_col].astype("string").map(
        lambda value: bool(order_pattern.fullmatch(str(value).strip()))
        if pd.notna(value) else False
    )
    lines = raw.loc[valid_order].copy()
    if lines.empty:
        raise MonthlySalesRevenueError("No sales lines remain after structural filtering")
    lines[order_col] = lines[order_col].astype(str).str.strip()
    lines["_order_date"] = pd.to_datetime(
        lines[date_col], dayfirst=True, errors="coerce"
    ).dt.date
    lines["_line_amount_vnd"] = lines[amount_col].map(parse_vnd)
    if lines["_order_date"].isna().any():
        raise MonthlySalesRevenueError("Sales lines contain unparseable order dates")
    if lines["_line_amount_vnd"].isna().any():
        raise MonthlySalesRevenueError("Sales lines contain non-integer or unparseable VND")
    if lines[status_col].isna().any():
        raise MonthlySalesRevenueError("Sales lines contain null statuses")
    if lines[product_col].isna().any():
        raise MonthlySalesRevenueError("Sales lines contain null product names")

    raw_columns = [column for column in raw.columns if not str(column).startswith("_source_")]
    duplicate_subset = raw_columns + ["_source_file", "_source_sheet_or_table"]
    duplicate_mask = lines.duplicated(duplicate_subset, keep="first")
    duplicates_removed = int(duplicate_mask.sum())
    lines = lines.loc[~duplicate_mask].copy()
    lines["_normalized_status"] = (
        lines[status_col].astype(str).str.strip().str.casefold().str.replace(r"\s+", " ", regex=True)
    )
    lines["_fragment"] = (
        lines["_source_file"].astype(str) + "::" + lines["_source_sheet_or_table"].astype(str)
    )
    grouped = lines.groupby(order_col, sort=False)
    date_conflicts = grouped["_order_date"].nunique(dropna=False).ne(1)
    status_conflicts = grouped["_normalized_status"].nunique(dropna=False).ne(1)
    cross_fragment = grouped["_fragment"].nunique(dropna=False).ne(1)
    if date_conflicts.any():
        raise MonthlySalesRevenueError(
            f"Conflicting dates for {int(date_conflicts.sum())} order IDs"
        )
    if status_conflicts.any():
        raise MonthlySalesRevenueError(
            f"Conflicting statuses for {int(status_conflicts.sum())} order IDs"
        )
    if cross_fragment.any():
        raise MonthlySalesRevenueError(
            f"Order IDs span fragments: {int(cross_fragment.sum())}"
        )

    coverage_start = date.fromisoformat(monthly["data_start"])
    coverage_end = date.fromisoformat(monthly["data_end"])
    actual_start = min(lines["_order_date"])
    actual_end = max(lines["_order_date"])
    if (actual_start, actual_end) != (coverage_start, coverage_end):
        raise MonthlySalesRevenueError(
            "Configured data coverage does not match loaded order dates: "
            f"configured={coverage_start}..{coverage_end}, actual={actual_start}..{actual_end}"
        )
    source_files = sorted(set(lines["_source_file"].astype(str)))
    source_sheets = sorted(
        {
            f"{Path(file_name).name}::{sheet}"
            for file_name, sheet in zip(
                lines["_source_file"], lines["_source_sheet_or_table"], strict=True
            )
        }
    )
    evidence = {
        "rows_loaded": int(len(raw)),
        "structural_rows_excluded": int((~valid_order).sum()),
        "valid_line_rows_before_dedup": int(valid_order.sum()),
        "duplicate_export_rows_removed": duplicates_removed,
        "rows_after_dedup": int(len(lines)),
        "distinct_orders_loaded": int(lines[order_col].nunique()),
        "source_files": source_files,
        "provenance_sources": source_files,
        "source_sheets": source_sheets,
        "data_coverage": {
            "start": coverage_start.isoformat(), "end": coverage_end.isoformat()
        },
    }
    _LINE_CACHE[cache_key] = (lines.copy(), evidence)
    return lines, json.loads(json.dumps(evidence, ensure_ascii=False))


def calculate_monthly_sales_revenue(
    config: dict[str, Any], data_root: str | Path, period: Period, ruleset: str
) -> dict[str, Any]:
    """Sum eligible line amounts for one already-resolved inclusive flow period."""
    if ruleset not in {"train", "public_test"} or config.get("split") != ruleset:
        raise MonthlySalesRevenueError("Config split and requested ruleset do not match")
    if config.get("archetype") != "monthly_excel_sales_lines":
        raise MonthlySalesRevenueError("Business is not configured for monthly Excel sales lines")
    monthly = config.get("monthly_sales", {})
    if monthly.get("revenue_enabled") is not True:
        raise MonthlySalesRevenueError("Direct revenue is not enabled for this business")
    if not isinstance(period, Period) or period.mode != "flow" or period.end < period.start:
        raise MonthlySalesRevenueError("Revenue requires a valid resolved flow period")

    coverage_start = date.fromisoformat(monthly["data_start"])
    coverage_end = date.fromisoformat(monthly["data_end"])
    if period.end < coverage_start or period.start > coverage_end:
        raise MonthlySalesRevenueError("Resolved period is outside verified data coverage")
    lines, load_evidence = _prepare_lines(config, data_root)
    source = config["sources"][monthly["source"]]
    semantic = source["semantic_columns"]
    order_col = semantic["order_id"]
    status_col = semantic["status"]

    in_period = lines["_order_date"].map(period.includes)
    period_lines = lines.loc[in_period].copy()
    order_status = period_lines.drop_duplicates(order_col, keep="first")[[order_col, status_col]]
    order_status["_eligible"] = order_status[status_col].map(
        lambda value: revenue_eligible(value, ruleset)
    )
    eligible_ids = set(order_status.loc[order_status["_eligible"], order_col])
    eligible_lines = period_lines.loc[period_lines[order_col].isin(eligible_ids)]
    total = sum(
        (Decimal(int(value)) for value in eligible_lines["_line_amount_vnd"]),
        Decimal(0),
    )
    excluded = order_status.loc[~order_status["_eligible"]]
    effective_start = max(period.start, coverage_start)
    effective_end = min(period.end, coverage_end)
    evidence = {
        "business_id": config["business_id"],
        "ruleset": ruleset,
        "rule_source": f"{ruleset}/rulebook.md §1; {ruleset}/{config['readme']}",
        "grain": "one row per order product line",
        "date_basis": semantic["order_date"],
        "amount_column": semantic["line_amount"],
        "amount_basis": "sum line amounts after line discount",
        "period": {
            "start": period.start.isoformat(),
            "end": period.end.isoformat(),
            "inclusive": True,
        },
        "effective_period_within_coverage": {
            "start": effective_start.isoformat(), "end": effective_end.isoformat()
        },
        **load_evidence,
        "rows_in_period_all_statuses": int(len(period_lines)),
        "distinct_orders_in_period_all_statuses": int(period_lines[order_col].nunique()),
        "eligible_rows_after_status_filter": int(len(eligible_lines)),
        "eligible_distinct_orders": int(len(eligible_ids)),
        "excluded_rows_by_status": int(len(period_lines) - len(eligible_lines)),
        "excluded_distinct_orders": int(len(excluded)),
        "eligible_statuses": sorted(
            set(order_status.loc[order_status["_eligible"], status_col].astype(str))
        ),
        "excluded_statuses": sorted(set(excluded[status_col].astype(str))),
        "total": int(total),
    }
    return {"type": "number", "value": int(total), "evidence": evidence}
