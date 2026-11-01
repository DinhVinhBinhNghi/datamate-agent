"""Audit configured monthly Excel sales-line sources without answering questions."""

from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

from datamate.load_business import read_config
from datamate.readers import load_source


REQUIRED_ROLES = {"order_id", "order_date", "status", "product_name", "line_amount"}


def parse_vnd(value: Any) -> int | None:
    """Parse integer VND values used by this archetype; return None on ambiguity."""
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
        amount = Decimal(text) * multiplier
    except InvalidOperation:
        return None
    return int(amount) if amount == amount.to_integral_value() else None


def _fragment_label(row: pd.Series) -> str:
    return f"{Path(str(row['_source_file'])).name}::{row['_source_sheet_or_table']}"


def _expect(actual: Any, expected: Any) -> bool:
    return actual == expected


def audit_business(root: Path, split: str, business_id: str) -> dict[str, Any]:
    config_root = root / "configs/businesses"
    config = read_config(split, business_id, config_root)
    monthly = config.get("monthly_sales")
    if not isinstance(monthly, dict):
        raise ValueError(f"{split}/{business_id} has no monthly_sales config")
    source_name = monthly.get("source")
    source = config["sources"].get(source_name)
    if not isinstance(source, dict):
        raise ValueError(f"{split}/{business_id} monthly_sales source is invalid")
    semantic = source.get("semantic_columns", {})
    missing_roles = sorted(REQUIRED_ROLES - set(semantic))
    if missing_roles:
        raise ValueError(f"{split}/{business_id} missing semantic roles: {missing_roles}")

    data = load_source(config, source_name, root / split)
    order_col = semantic["order_id"]
    date_col = semantic["order_date"]
    status_col = semantic["status"]
    product_col = semantic["product_name"]
    amount_col = semantic["line_amount"]
    order_pattern = re.compile(monthly["order_id_pattern"])
    valid_order = data[order_col].astype("string").map(
        lambda value: bool(order_pattern.fullmatch(str(value))) if pd.notna(value) else False
    )
    lines = data.loc[valid_order].copy()
    lines["_parsed_date"] = pd.to_datetime(
        lines[date_col], dayfirst=True, errors="coerce"
    )
    lines["_parsed_amount"] = lines[amount_col].map(parse_vnd)
    lines["_fragment"] = lines.apply(_fragment_label, axis=1)

    grouped = lines.groupby(order_col, dropna=False)
    order_sizes = grouped.size()
    multi_ids = order_sizes[order_sizes > 1].index
    varying_amounts = grouped["_parsed_amount"].nunique(dropna=False).reindex(multi_ids)
    cross_fragment = grouped["_fragment"].nunique().gt(1)
    date_conflicts = grouped["_parsed_date"].nunique(dropna=False).gt(1)
    status_conflicts = grouped[status_col].nunique(dropna=False).gt(1)
    raw_columns = [column for column in data.columns if not str(column).startswith("_source_")]
    duplicate_extra = int(lines.duplicated(raw_columns, keep="first").sum())

    readme_path = root / split / config["readme"]
    readme = readme_path.read_text(encoding="utf-8").lower()
    line_semantics_from_readme = "tổng tiền" in readme and "thành tiền sau giảm" in readme
    statuses = {
        str(key): int(value)
        for key, value in lines[status_col].value_counts(dropna=False).sort_index().items()
    }
    fragment_rows = {
        str(key): int(value)
        for key, value in lines["_fragment"].value_counts().sort_index().items()
    }
    date_min = lines["_parsed_date"].min()
    date_max = lines["_parsed_date"].max()
    actual = {
        "source_fragment_count": int(lines["_fragment"].nunique()),
        "row_count_before_filter": int(len(data)),
        "row_count_after_structural_filter": int(len(lines)),
        "structural_rows_excluded": int((~valid_order).sum()),
        "distinct_orders": int(lines[order_col].nunique()),
        "date_start": date_min.date().isoformat() if pd.notna(date_min) else None,
        "date_end": date_max.date().isoformat() if pd.notna(date_max) else None,
        "invalid_dates": int(lines["_parsed_date"].isna().sum()),
        "invalid_line_amounts": int(lines["_parsed_amount"].isna().sum()),
        "missing_products": int(lines[product_col].isna().sum()),
        "cross_fragment_order_ids": int(cross_fragment.sum()),
        "order_date_conflicts": int(date_conflicts.sum()),
        "order_status_conflicts": int(status_conflicts.sum()),
        "duplicate_export_rows_extra": duplicate_extra,
        "status_counts": statuses,
    }
    expectations = config.get("audit_expectations", {})
    expectation_checks = {
        key: _expect(actual.get(key), expected) for key, expected in expectations.items()
    }
    invariant_checks = {
        "semantic_roles_complete": not missing_roles,
        "all_dates_parse": actual["invalid_dates"] == 0,
        "all_line_amounts_parse_to_integer_vnd": actual["invalid_line_amounts"] == 0,
        "all_products_present": actual["missing_products"] == 0,
        "no_order_crosses_fragments": actual["cross_fragment_order_ids"] == 0,
        "one_date_per_order": actual["order_date_conflicts"] == 0,
        "one_status_per_order": actual["order_status_conflicts"] == 0,
        "no_exact_export_duplicate": duplicate_extra == 0,
        "readme_declares_line_amount_after_discount": line_semantics_from_readme,
        "config_declares_line_grain": monthly.get("grain") == "order_product_line",
        "config_declares_line_amount": monthly.get("line_amount_semantics")
        == "line_amount_after_discount",
    }
    return {
        "split": split,
        "business_id": business_id,
        "archetype": config.get("archetype"),
        "layout": {
            "format": source.get("format"),
            "path": source.get("path") or source.get("path_glob"),
            "sheet": source.get("sheet"),
            "sheet_pattern": source.get("sheet_pattern"),
            "header_row_zero_based": source.get("header_row", 0),
            "forward_fill_columns": source.get("forward_fill_columns", []),
        },
        "metrics": actual,
        "status_counts": statuses,
        "fragment_rows": fragment_rows,
        "line_amount_evidence": {
            "readme_declares_total_is_line_amount_after_discount": line_semantics_from_readme,
            "multi_line_orders": int(len(multi_ids)),
            "multi_line_orders_with_varying_line_amount": int(varying_amounts.gt(1).sum()),
            "multi_line_orders_with_same_line_amount": int(varying_amounts.eq(1).sum()),
            "systematic_repeated_order_total_detected": bool(
                len(multi_ids) and varying_amounts.gt(1).sum() == 0
            ),
        },
        "checks": {**invariant_checks, **{f"expected_{k}": v for k, v in expectation_checks.items()}},
        "passed": all(invariant_checks.values()) and all(expectation_checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--business", action="append", required=True, help="split/business_id"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    reports = []
    for item in args.business:
        split, business_id = item.split("/", 1)
        reports.append(audit_business(root, split, business_id))
    result = {
        "audit": "wave1_monthly_excel_sales_archetype",
        "businesses": reports,
        "comparison": [
            {
                "business_id": report["business_id"],
                **report["layout"],
                "rows": report["metrics"]["row_count_after_structural_filter"],
                "orders": report["metrics"]["distinct_orders"],
                "date_start": report["metrics"]["date_start"],
                "date_end": report["metrics"]["date_end"],
                "fragments": report["metrics"]["source_fragment_count"],
            }
            for report in reports
        ],
        "public_revenue_enabled": False,
        "passed": all(report["passed"] for report in reports),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
