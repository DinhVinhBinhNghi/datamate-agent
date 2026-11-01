from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from datamate.business.public_dev002 import calculate_dev002, collapse_order_headers
from datamate.planner.heuristic import plan_heuristic
from datamate.planner.validate import PlannerFailure


CONFIG = {
    "split": "public_test",
    "business_id": "dev_002",
    "sources": {"orders": {"semantic_columns": {
        "order_id": "Mã đơn hàng", "order_date": "Ngày đặt hàng",
        "status": "Trạng thái đơn hàng",
    }}},
    "order_header": {
        "order_id_pattern": "^ORD[0-9]+$",
        "data_start": "2025-01-01", "data_end": "2026-05-24",
    },
}


def _lines() -> pd.DataFrame:
    rows = [
        ("ORD1", "01/01/2025", "Đã hoàn thành", "a", 5),
        ("ORD1", pd.Timestamp("2025-01-01"), "Đã hoàn thành", "b", 6),
        ("ORD2", "02/01/2025", "Đã hủy", "c", 7),
        ("ORD3", "02/01/2025", "Đã hoàn hàng", "d", 8),
        ("Mã đơn hàng", "Ngày đặt hàng", "Trạng thái đơn hàng", "Tên sản phẩm", 9),
        (None, None, None, None, 10),
    ]
    return pd.DataFrame(rows, columns=[
        "Mã đơn hàng", "Ngày đặt hàng", "Trạng thái đơn hàng",
        "Tên sản phẩm", "_source_row",
    ]).assign(_source_file="public_test/data/dev_002/BanHang_T1_2025.xlsx",
             _source_sheet_or_table="DonHang_ChiTiet")


def test_collapse_verifies_header_grain_and_excludes_structural_rows():
    headers, evidence = collapse_order_headers(_lines(), CONFIG)
    assert list(headers["Mã đơn hàng"]) == ["ORD1", "ORD2", "ORD3"]
    assert evidence["raw_order_line_rows"] == 6
    assert evidence["structural_rows_excluded"] == 2
    assert evidence["order_headers_after_collapse"] == 3


@pytest.mark.parametrize(
    ("operation", "expected_type", "expected_value"),
    [("order_count", "number", 1), ("cancel_count", "number", 1),
     ("cancel_rate", "percent", 33.33)],
)
def test_public_dev002_operations(operation, expected_type, expected_value):
    with patch("datamate.business.public_dev002.load_source", return_value=_lines()):
        result = calculate_dev002(CONFIG, Path("public_test"), "tháng 1/2025", "2025-01-31", operation)
    assert result["type"] == expected_type
    assert result["value"] == expected_value
    assert result["evidence"]["orders_in_period_all_statuses"] == 3
    assert result["evidence"]["returned_orders_not_counted_as_cancelled"] == 1


@pytest.mark.parametrize(
    ("text", "family", "period"),
    [
        ("Hom ni quan duoc may don roi?", "order_count", "hôm nay"),
        ("Hôm qua có mấy đơn rứa?", "order_count", "hôm qua"),
        ("Quý 2/2025 quán có mấy đơn rứa?", "order_count", "quý 2/2025"),
        ("Thang 6 nam 2025 quan co may don bi huy?", "cancel_count", "tháng 6/2025"),
        ("2/25 bi huy bao nhieu don?", "cancel_count", "tháng 2/2025"),
        ("Tỉ lệ đh huỷ T4/2025 bnhiu % z?", "cancel", "tháng 4/2025"),
    ],
)
def test_public_dev002_planner_templates(text, family, period):
    intent = plan_heuristic({
        "id": "fixture", "business_id": "dev_002", "question": text,
        "as_of_date": "2026-05-24",
    })
    assert intent.ruleset == "public_test"
    assert intent.family == family
    assert intent.period_expression == period


def test_public_dev002_unenabled_family_fails_closed():
    with pytest.raises(PlannerFailure):
        plan_heuristic({
            "id": "fixture", "business_id": "dev_002",
            "question": "Doanh thu tháng 1/2025 là bao nhiêu?",
            "as_of_date": "2026-05-24",
        })


def test_train_template_regression_is_unchanged():
    intent = plan_heuristic({
        "id": "fixture", "business_id": "biz_129",
        "question": "doanh thu tháng 3/2026 là bao nhiêu?",
        "as_of_date": "2026-03-31",
    })
    assert (intent.ruleset, intent.family, intent.period_expression) == (
        "train", "revenue", "tháng 3/2026"
    )
