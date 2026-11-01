from datetime import date
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from datamate.business.monthly_sales_revenue import (
    MonthlySalesRevenueError,
    _LINE_CACHE,
    calculate_monthly_sales_revenue,
    parse_vnd,
)
from datamate.business.status import is_returned, revenue_eligible
from datamate.time.resolve import Period


def _config(split: str = "train", enabled: bool = True) -> dict:
    return {
        "split": split,
        "business_id": "fixture",
        "archetype": "monthly_excel_sales_lines",
        "readme": "data/fixture/README.md",
        "sources": {"orders": {
            "format": "xlsx_sheets",
            "path": "orders.xlsx",
            "semantic_columns": {
                "order_id": "order", "order_date": "date", "status": "status",
                "product_name": "product", "line_amount": "amount",
            },
        }},
        "monthly_sales": {
            "source": "orders", "grain": "order_product_line",
            "line_amount_semantics": "line_amount_after_discount",
            "order_id_pattern": "^ORD[0-9]+$", "data_start": "2025-01-01",
            "data_end": "2025-01-31", "revenue_enabled": enabled,
        },
    }


def _frame(rows: list[tuple]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["order", "date", "status", "product", "amount"])
    frame["_source_file"] = "orders.xlsx"
    frame["_source_sheet_or_table"] = "01.2025"
    frame["_source_row"] = range(2, len(frame) + 2)
    return frame


def _calculate(rows: list[tuple], config: dict | None = None):
    _LINE_CACHE.clear()
    root = Path.cwd()
    source_file = root / "orders.xlsx"
    effective_config = deepcopy(config or _config())
    valid_dates = [
        pd.Timestamp(row[1]).date() if not isinstance(row[1], str)
        else pd.to_datetime(row[1], dayfirst=True).date()
        for row in rows if isinstance(row[0], str) and row[0].startswith("ORD")
    ]
    if effective_config["monthly_sales"].get("revenue_enabled") is True:
        effective_config["monthly_sales"]["data_start"] = min(valid_dates).isoformat()
        effective_config["monthly_sales"]["data_end"] = max(valid_dates).isoformat()
    with patch("datamate.business.monthly_sales_revenue._source_signature", return_value=((str(source_file), 1, 1),)), patch(
        "datamate.business.monthly_sales_revenue.load_source", return_value=_frame(rows)
    ):
        return calculate_monthly_sales_revenue(
            effective_config, root, Period(date(2025, 1, 1), date(2025, 1, 31)),
            effective_config["split"],
        )


def test_direct_revenue_excludes_whole_cancelled_and_returned_orders():
    rows = [
        ("ORD1", "01/01/2025", "Đã hoàn thành", "A", "100"),
        ("ORD1", "01/01/2025", "Đã hoàn thành", "B", "200"),
        ("ORD1", "01/01/2025", "Đã hoàn thành", "B", "200"),
        ("ORD2", "02/01/2025", "Đã hủy", "C", "500"),
        ("ORD3", "03/01/2025", "Hoàn trả", "D", "700"),
        ("ORD4", "04/01/2025", "Đang giao dịch", "E", "30"),
        (None, None, None, None, "9999"),
        ("ORD5", "01/02/2025", "Đã hoàn thành", "F", "1000"),
    ]
    result = _calculate(rows)
    assert result["value"] == 330
    evidence = result["evidence"]
    assert evidence["structural_rows_excluded"] == 1
    assert evidence["duplicate_export_rows_removed"] == 1
    assert evidence["eligible_distinct_orders"] == 2
    assert evidence["excluded_distinct_orders"] == 2
    assert evidence["excluded_statuses"] == ["Hoàn trả", "Đã hủy"]
    assert evidence["total"] == 330


@pytest.mark.parametrize("parts", [[500], [200, 300], [0, 100, 400]])
def test_line_partition_preserves_direct_revenue(parts):
    rows = [
        ("ORD1", "05/01/2025", "Thành công", f"P{i}", amount)
        for i, amount in enumerate(parts)
    ]
    assert _calculate(rows)["value"] == 500


@pytest.mark.parametrize("status", ["Đã hủy đơn", "hàng trả về", "Hoàn trả"])
def test_excluded_order_contributes_zero_for_any_return_or_cancel_variant(status):
    rows = [("ORD1", "05/01/2025", status, "P", 500)]
    assert _calculate(rows)["value"] == 0


def test_status_variants_and_in_delivery_follow_rulebook():
    assert is_returned("hàng trả về", "train")
    assert is_returned("Hoàn trả", "train")
    assert revenue_eligible("Đang giao dịch", "train")


def test_public_config_remains_fail_closed_until_train_validation():
    config = _config(split="public_test", enabled=False)
    with pytest.raises(MonthlySalesRevenueError, match="not enabled"):
        _calculate([("ORD1", "01/01/2025", "Đã hoàn thành", "A", 100)], config)


def test_conflicting_status_within_order_fails_closed():
    rows = [
        ("ORD1", "01/01/2025", "Đã hoàn thành", "A", 100),
        ("ORD1", "01/01/2025", "Đã hủy", "B", 200),
    ]
    with pytest.raises(MonthlySalesRevenueError, match="Conflicting statuses"):
        _calculate(rows)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("38,000", 38000), ("10.000đ", 10000), ("105k", 105000), ("1,5k", 1500)],
)
def test_verified_vnd_formats_are_exact_integers(raw, expected):
    assert parse_vnd(raw) == expected
