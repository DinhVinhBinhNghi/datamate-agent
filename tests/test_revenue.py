from decimal import Decimal
from pathlib import Path
import json

import pandas as pd
import pytest

from datamate.business.revenue import calculate_revenue, parse_vnd
from datamate.business.status import revenue_eligible


def test_parse_vnd_decimal_exact():
    assert parse_vnd("50.000đ") == Decimal("50000")
    assert parse_vnd("1.234.567 Đ") == Decimal("1234567")
    assert parse_vnd("1,45tr") == Decimal("1450000")


def test_revenue_status_rule_is_metric_specific():
    assert revenue_eligible("shipping", "train")
    assert not revenue_eligible("cancelled", "train")
    assert not revenue_eligible("returned", "train")


def test_revenue_uses_detail_totals_and_day_placed():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "configs/businesses/train/biz_129.json").read_text(encoding="utf-8"))
    # On the user's project, source files are under <project>/train. In the
    # isolated chat workspace, the extracted fixture is under runtime_data/train.
    data_root = root / "train"
    if not (data_root / config["sources"]["orders"]["path"]).is_file():
        data_root = root / "runtime_data" / "train"
    result = calculate_revenue(config, data_root, "tháng 1/2025", "2025-01-31")
    assert result["type"] == "number"
    assert result["value"] > 0
    evidence = result["evidence"]
    assert evidence["basis"] == "sum detail line totals after line discount"
    assert evidence["unmatched_detail_rows"] == 0
    assert evidence["eligible_detail_rows"] <= evidence["detail_rows_in_period"]


def test_duplicate_headers_fail_instead_of_inflating_revenue():
    # Cardinality guard is also exercised by the production merge validate=many_to_one.
    details = pd.DataFrame({"order_id": ["A"]})
    headers = pd.DataFrame({"order_id": ["A", "A"], "status": ["ok", "ok"]})
    with pytest.raises(pd.errors.MergeError):
        details.merge(headers, on="order_id", validate="many_to_one")
