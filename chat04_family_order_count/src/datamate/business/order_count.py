"""Order-count calculation for verified train/biz_129 data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from datamate.business.status import order_count_eligible
from datamate.load_business import ConfigError, read_config
from datamate.readers import SourceLoadError, load_source
from datamate.time.resolve import PeriodResolutionError, resolve_period


RULE_SOURCE = "train/rulebook.md §1; train/data/biz_129/README.md"


def calculate_order_count(
    config: dict[str, Any], data_root: str | Path, period_expression: str, as_of_date: str
) -> dict[str, Any]:
    if (config.get("split"), config.get("business_id")) != ("train", "biz_129"):
        raise ValueError("Order-count operation currently supports train/biz_129 only")
    orders = load_source(config, "orders", data_root)
    period = resolve_period(period_expression, as_of_date, None, "train")
    order_id, date_col, status_col = "Số phiếu", "Ngày bán", "Tình trạng đơn"
    if orders[order_id].isna().any() or orders[order_id].duplicated().any():
        raise ValueError("Order header key must be unique and non-null before counting")
    dates = pd.to_datetime(orders[date_col], errors="coerce").dt.date
    if dates.isna().any():
        raise ValueError("Order date contains unparseable values")
    in_period = dates.map(lambda d: period.start <= d <= period.end)
    eligible = orders[status_col].map(lambda s: order_count_eligible(s, "train"))
    selected = orders[in_period & eligible]
    return {
        "type": "number",
        "value": int(selected[order_id].nunique()),
        "evidence": {
            "business_id": "biz_129",
            "ruleset": "train",
            "rule_source": RULE_SOURCE,
            "period": {"start": period.start.isoformat(), "end": period.end.isoformat(), "inclusive": True},
            "grain": "one row per order header",
            "count_key": order_id,
            "orders_total": int(len(orders)),
            "orders_in_period_all_statuses": int(in_period.sum()),
            "eligible_orders": int(len(selected)),
            "eligible_statuses": sorted(set(orders.loc[in_period & eligible, status_col].astype(str))),
            "excluded_statuses": sorted(set(orders.loc[in_period & ~eligible, status_col].astype(str))),
            "null_order_keys": int(orders[order_id].isna().sum()),
            "duplicate_order_keys": int(orders[order_id].duplicated().sum()),
            "source": str(orders["_source_file"].iloc[0]) if len(orders) else None,
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
        result = calculate_order_count(config, args.data_root, args.period, args.as_of_date)
    except (ConfigError, SourceLoadError, PeriodResolutionError, ValueError, KeyError) as exc:
        print(f"ORDER COUNT FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
