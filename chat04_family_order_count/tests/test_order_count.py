from pathlib import Path
import json

from datamate.business.order_count import calculate_order_count


def test_order_count_uses_header_grain_and_train_status_rule():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "configs/businesses/train/biz_129.json").read_text(encoding="utf-8"))
    data_root = root / "train"
    if not (data_root / config["sources"]["orders"]["path"]).is_file():
        data_root = root / "runtime_data" / "train"
    result = calculate_order_count(config, data_root, "tháng 1/2025", "2025-01-31")
    assert result["type"] == "number"
    assert result["value"] == 1841
    assert result["evidence"]["orders_in_period_all_statuses"] == 1880
    assert result["evidence"]["eligible_orders"] == 1841
    assert result["evidence"]["null_order_keys"] == 0
    assert result["evidence"]["duplicate_order_keys"] == 0
