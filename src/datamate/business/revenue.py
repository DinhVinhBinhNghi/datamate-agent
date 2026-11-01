"""Revenue calculation for verified train/biz_129 data."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

from datamate.business.status import revenue_eligible
from datamate.load_business import ConfigError, read_config
from datamate.readers import SourceLoadError, load_source
from datamate.time.resolve import PeriodResolutionError, resolve_period


RULE_SOURCE = "train/rulebook.md §1; train/data/biz_129/README.md"


def parse_vnd(value: Any) -> Decimal:
    """Parse observed integer-VND CSV display values without float conversion."""
    if value is None or pd.isna(value):
        raise ValueError("Revenue line total is null")
    text = str(value).strip().lower().replace("đ", "").replace("₫", "")
    text = re.sub(r"\s+", "", text)
    if text.endswith("tr"):
        number = text[:-2]
        if not re.fullmatch(r"\d+(?:[,.]\d+)?", number):
            raise ValueError(f"Unsupported VND value {value!r}")
        try:
            return Decimal(number.replace(",", ".")) * Decimal(1_000_000)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid VND value {value!r}") from exc
    if not re.fullmatch(r"-?[0-9.]+", text):
        raise ValueError(f"Unsupported VND value {value!r}")
    try:
        return Decimal(text.replace(".", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid VND value {value!r}") from exc


def calculate_revenue(
    config: dict[str, Any], data_root: str | Path, period_expression: str, as_of_date: str
) -> dict[str, Any]:
    if (config.get("split"), config.get("business_id")) != ("train", "biz_129"):
        raise ValueError("Revenue operation currently supports train/biz_129 only")
    if "revenue" not in config.get("rulesets", {"revenue": "train/rulebook.md §1"}):
        raise ValueError("Revenue ruleset is not declared in config")
    orders = load_source(config, "orders", data_root)
    lines = load_source(config, "order_lines", data_root)
    period = resolve_period(period_expression, as_of_date, None, "train")
    order_id = "Số phiếu"
    line_order_id = "Số CT"
    status_col = "Tình trạng đơn"
    date_col = "Ngày bán"
    amount_col = "Tiền bán"

    duplicate_headers = int(orders[order_id].dropna().duplicated().sum())
    if duplicate_headers:
        raise ValueError(f"Expected one header per order; found {duplicate_headers} duplicate keys")
    missing_header_keys = int((~lines[line_order_id].isin(orders[order_id])).sum())
    if missing_header_keys:
        raise ValueError(f"{missing_header_keys} detail rows have no matching order header")

    header_cols = [order_id, status_col, date_col]
    joined = lines.merge(
        orders[header_cols], left_on=line_order_id, right_on=order_id,
        how="left", validate="many_to_one", indicator=True,
    )
    if (joined["_merge"] != "both").any():
        raise ValueError("Unexpected unmatched order detail rows")
    order_dates = pd.to_datetime(joined[date_col], errors="coerce").dt.date
    if order_dates.isna().any():
        raise ValueError("Order date contains unparseable values")
    in_period = order_dates.map(lambda d: period.start <= d <= period.end)
    eligible = joined[status_col].map(lambda s: revenue_eligible(s, "train"))
    selected = joined[in_period & eligible]
    amount = sum((parse_vnd(x) for x in selected[amount_col]), Decimal(0))
    return {
        "type": "number",
        "value": int(amount),
        "evidence": {
            "business_id": "biz_129",
            "ruleset": "train",
            "rule_source": RULE_SOURCE,
            "period": {"start": period.start.isoformat(), "end": period.end.isoformat(), "inclusive": True},
            "basis": "sum detail line totals after line discount",
            "eligible_statuses": sorted(set(joined.loc[in_period & eligible, status_col].astype(str))),
            "excluded_statuses_in_period": sorted(set(joined.loc[in_period & ~eligible, status_col].astype(str))),
            "order_headers": int(len(orders)),
            "detail_rows_before_filter": int(len(lines)),
            "detail_rows_in_period": int(in_period.sum()),
            "eligible_detail_rows": int(len(selected)),
            "matched_detail_rows": int(len(joined)),
            "unmatched_detail_rows": 0,
            "amount_column": amount_col,
            "provenance_sources": sorted(set(lines["_source_file"].astype(str)) | set(orders["_source_file"].astype(str))),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", required=True)
    parser.add_argument("--data-root", type=Path, default=Path.cwd() / "train")
    parser.add_argument("--period", required=True)
    parser.add_argument("--as-of-date", required=True)
    args = parser.parse_args(argv)
    try:
        config = read_config("train", args.business_id)
        result = calculate_revenue(config, args.data_root, args.period, args.as_of_date)
    except (ConfigError, SourceLoadError, PeriodResolutionError, ValueError, KeyError) as exc:
        print(f"REVENUE FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
