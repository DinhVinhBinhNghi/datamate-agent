"""Load one configured source for a business and print a small quality summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from datamate.readers import SourceLoadError, load_source


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "configs" / "businesses"


class ConfigError(ValueError):
    """Raised when a business config or declared source does not match the data."""


def read_config(split: str, business_id: str, config_root: Path = CONFIG_ROOT) -> dict[str, Any]:
    path = config_root / split / f"{business_id}.json"
    if not path.is_file():
        raise ConfigError(f"Business config not found: {path}")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Cannot read config {path}: {exc}") from exc
    if config.get("split") != split or config.get("business_id") != business_id:
        raise ConfigError(
            f"Config identity mismatch in {path}: expected {split}/{business_id}, "
            f"got {config.get('split')}/{config.get('business_id')}"
        )
    if not isinstance(config.get("sources"), dict) or not config["sources"]:
        raise ConfigError(f"Config {path} must declare at least one source")
    return config


def _safe_sample(df: pd.DataFrame, order_key: str | None) -> list[dict[str, Any]]:
    sample = df.head(3).copy()
    redact = set(sample.columns) - {
        "Hình thức thanh toán", "Dư nợ", "Thanh toán", "Tình trạng đơn",
        "Phải thu", "Ngày bán", "Ngày", "Trạng thái", "Thành tiền",
        "_source_file", "_source_sheet_or_table", "_source_row"
    }
    if order_key:
        redact.add(order_key)
    for column in redact.intersection(sample.columns):
        sample[column] = sample[column].map(lambda value: "[redacted]" if pd.notna(value) else None)
    return sample.astype(object).where(pd.notna(sample), None).to_dict(orient="records")


def load_business(
    split: str,
    business_id: str,
    data_root: Path,
    config_root: Path = CONFIG_ROOT,
) -> dict[str, Any]:
    config = read_config(split, business_id, config_root)
    result: dict[str, Any] = {
        "business_id": business_id,
        "split": split,
        "sources": {},
    }
    for source_name, source in config["sources"].items():
        df = load_source(config, source_name, data_root)
        key = source.get("order_key")
        warnings = []
        null_counts = df.isna().sum()
        nonzero_nulls = {str(c): int(n) for c, n in null_counts.items() if n}
        if nonzero_nulls:
            warnings.append({"kind": "null_values", "counts": nonzero_nulls})
        if key:
            null_key_count = int(df[key].isna().sum())
            duplicate_key_count = int(df[key].dropna().duplicated().sum())
            if null_key_count:
                warnings.append({"kind": "null_order_key", "column": key, "count": null_key_count})
            if duplicate_key_count:
                warnings.append({"kind": "duplicate_order_key", "column": key, "count": duplicate_key_count})
        result["sources"][source_name] = {
            "path": source["path"],
            "format": source["format"],
            "row_count": int(len(df)),
            "columns": [str(c) for c in df.columns],
            "dtypes": {str(c): str(dtype) for c, dtype in df.dtypes.items()},
            "order_key": key,
            "order_key_null_count": int(df[key].isna().sum()) if key else None,
            "order_key_duplicate_count": int(df[key].dropna().duplicated().sum()) if key else None,
            "sample_safe": _safe_sample(df, key),
            "quality_warnings": warnings,
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=("train", "public_test"))
    parser.add_argument("--business-id", required=True)
    parser.add_argument(
        "--data-root",
        type=Path,
        help="Split root containing data/<business_id>; defaults to <cwd>/<split>",
    )
    parser.add_argument("--config-root", type=Path, default=CONFIG_ROOT)
    args = parser.parse_args(argv)
    data_root = args.data_root or (Path.cwd() / args.split)
    try:
        summary = load_business(args.split, args.business_id, data_root, args.config_root)
    except (ConfigError, SourceLoadError, KeyError, TypeError) as exc:
        print(f"LOAD FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
