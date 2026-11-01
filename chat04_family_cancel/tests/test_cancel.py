from pathlib import Path
import json

from datamate.business.cancel import calculate_cancellations


def test_cancel_rate_denominator_includes_all_statuses():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "configs/businesses/train/biz_129.json").read_text(encoding="utf-8"))
    data_root = root / "train"
    if not (data_root / config["sources"]["orders"]["path"]).is_file():
        data_root = root / "runtime_data" / "train"
    result = calculate_cancellations(config, data_root, "tháng 1/2025", "2025-01-31")
    evidence = result["evidence"]
    assert evidence["orders_in_period_all_statuses"] == 1880
    assert evidence["cancelled_orders"] == 36
    assert evidence["returned_orders_not_counted_as_cancelled"] == 3
    assert result["value"] == 1.91
