"""Cancellation count and rate for verified train/biz_129 data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from datamate.business.status import is_cancelled
from datamate.load_business import ConfigError, read_config
from datamate.readers import SourceLoadError, load_source
from datamate.time.resolve import PeriodResolutionError, resolve_period


RULE_SOURCE = "train/rulebook.md §1 (cancel definition and cancellation-rate denominator); train/data/biz_129/README.md"


def calculate_cancellations(
    config: dict[str, Any], data_root: str | Path, period_expression: str, as_of_date: str
) -> dict[str, Any]:
    if (config.get("split"), config.get("business_id")) != ("train", "biz_129"):
        raise ValueError("Cancel operation currently supports train/biz_129 only")
    orders = load_source(config, "orders", data_root)
    period = resolve_period(period_expression, as_of_date, None, "train")
    key, date_col, status_col = "Số phiếu", "Ngày bán", "Tình trạng đơn"
    if orders[key].isna().any() or orders[key].duplicated().any():
        raise ValueError("Order header key must be unique and non-null before counting cancellations")
    dates = pd.to_datetime(orders[date_col], errors="coerce").dt.date
    if dates.isna().any():
        raise ValueError("Order date contains unparseable values")
    in_period = dates.map(lambda d: period.start <= d <= period.end)
    period_orders = orders[in_period]
    cancelled = period_orders[status_col].map(lambda s: is_cancelled(s, "train"))
    cancelled_count = int(cancelled.sum())
    denominator = int(len(period_orders))
    rate = round(cancelled_count * 100 / denominator, 2) if denominator else None
    return {
        "type": "unanswerable" if rate is None else "percent",
        "value": None if rate is None else rate,
        "evidence": {
            "business_id": "biz_129",
            "ruleset": "train",
            "rule_source": RULE_SOURCE,
            "period": {"start": period.start.isoformat(), "end": period.end.isoformat(), "inclusive": True},
            "count_key": key,
            "orders_in_period_all_statuses": denominator,
            "cancelled_orders": cancelled_count,
            "returned_orders_not_counted_as_cancelled": int(period_orders[status_col].map(lambda s: "return" in str(s).casefold() or "trả hàng" in str(s).casefold()).sum()),
            "cancel_rate_percent": rate,
            "rounding": "2 decimal places",
            "null_order_keys": int(orders[key].isna().sum()),
            "duplicate_order_keys": int(orders[key].duplicated().sum()),
            "source": str(orders["_source_file"].iloc[0]) if len(orders) else None,
            "unsupported_reason": "denominator is zero" if denominator == 0 else None,
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
        result = calculate_cancellations(config, args.data_root, args.period, args.as_of_date)
    except (ConfigError, SourceLoadError, PeriodResolutionError, ValueError, KeyError) as exc:
        print(f"CANCEL OPERATION FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
