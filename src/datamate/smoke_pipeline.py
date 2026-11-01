"""Run one deterministic loader/JOIN smoke check and write JSON evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from datamate.joins import JoinValidationError, sum_header_measure_once, validated_join
from datamate.load_business import CONFIG_ROOT, ConfigError, read_config
from datamate.readers import SourceLoadError, load_source


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_smoke(split: str, business_id: str, data_root: Path, output_dir: Path) -> dict:
    config = read_config(split, business_id)
    if business_id != "biz_123" or "orders_to_order_lines" not in config.get("joins", {}):
        raise ConfigError(
            "Current Group 3 smoke supports verified join train/biz_123/orders_to_order_lines"
        )
    orders = load_source(config, "orders", data_root)
    lines = load_source(config, "order_lines", data_root)
    joined, join_diagnostics = validated_join(
        config, "orders_to_order_lines", orders, lines
    )
    header_total = sum_header_measure_once(orders, "MaHoaDon", "TongThanhToan")
    result = {
        "business_id": business_id,
        "split": split,
        "operation": "load_and_validate_orders_to_order_lines",
        "source_counts": {"orders": int(len(orders)), "order_lines": int(len(lines))},
        "joined_row_count": int(len(joined)),
        "header_total_sum_pre_join": int(header_total),
        "header_total_summed_from": "orders_before_join",
        "join_diagnostics": join_diagnostics,
        "provenance_columns_present": {
            "orders": all(c in orders for c in ("_source_file", "_source_sheet_or_table", "_source_row")),
            "order_lines": all(c in lines for c in ("_source_file", "_source_sheet_or_table", "_source_row")),
        },
    }
    quality = {
        "business_id": business_id,
        "split": split,
        "checks": {
            "orders_key_null_count": int(orders["MaHoaDon"].isna().sum()),
            "orders_key_duplicate_count": int(orders["MaHoaDon"].dropna().duplicated().sum()),
            "order_lines_key_null_count": int(lines["MaHoaDon"].isna().sum()),
            "unmatched_left_distinct_keys": join_diagnostics["unmatched_left_distinct_keys"],
            "unmatched_right_distinct_keys": join_diagnostics["unmatched_right_distinct_keys"],
        },
    }
    _write_json(output_dir / "smoke_result.json", result)
    _write_json(output_dir / "quality_report.json", quality)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=("train", "public_test"))
    parser.add_argument("--business-id", required=True)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts") / "loader")
    args = parser.parse_args(argv)
    data_root = args.data_root or (Path.cwd() / args.split)
    try:
        result = run_smoke(args.split, args.business_id, data_root, args.output_dir)
    except (ConfigError, SourceLoadError, JoinValidationError, KeyError, TypeError) as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
