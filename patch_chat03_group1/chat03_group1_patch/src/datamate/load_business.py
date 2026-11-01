"""Load one configured source for a business and print a small quality summary."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "configs" / "businesses"


class ConfigError(ValueError):
    """Raised when a business config or declared source does not match the data."""


def _read_config(split: str, business_id: str, config_root: Path) -> dict[str, Any]:
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


def _load_csv_source(data_root: Path, source_name: str, source: dict[str, Any]) -> pd.DataFrame:
    source_path = data_root / source["path"]
    if not source_path.is_file():
        raise ConfigError(f"Source '{source_name}' file does not exist: {source_path}")
    if source.get("format") != "csv":
        raise ConfigError(
            f"Source '{source_name}' has unsupported format {source.get('format')!r}; "
            "Chat 3 Group 1 currently supports CSV only"
        )
    try:
        columns = pd.read_csv(
            source_path,
            encoding=source.get("encoding", "utf-8-sig"),
            sep=source.get("delimiter", ","),
            header=source.get("header_row", 0),
            nrows=0,
        ).columns.tolist()
    except Exception as exc:
        raise ConfigError(f"Cannot inspect source '{source_name}' at {source_path}: {exc}") from exc

    declared = source.get("semantic_columns", {})
    missing = [column for column in declared.values() if column not in columns]
    order_key = source.get("order_key")
    if order_key and order_key not in columns and order_key not in missing:
        missing.append(order_key)
    if missing:
        raise ConfigError(
            f"Source '{source_name}' at {source_path} is missing configured columns: "
            f"{missing}; found headers: {columns}"
        )
    try:
        return pd.read_csv(
            source_path,
            encoding=source.get("encoding", "utf-8-sig"),
            sep=source.get("delimiter", ","),
            header=source.get("header_row", 0),
        )
    except Exception as exc:
        raise ConfigError(f"Cannot load source '{source_name}' at {source_path}: {exc}") from exc


def _safe_sample(df: pd.DataFrame, order_key: str | None) -> list[dict[str, Any]]:
    sample = df.head(3).copy()
    redact = {
        c for c in sample.columns
        if re.search(r"mã|ma\b|số điện thoại|phone|email|tên|name", str(c), re.I)
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
    config = _read_config(split, business_id, config_root)
    result: dict[str, Any] = {
        "business_id": business_id,
        "split": split,
        "sources": {},
    }
    for source_name, source in config["sources"].items():
        df = _load_csv_source(data_root, source_name, source)
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
    except (ConfigError, KeyError, TypeError) as exc:
        print(f"LOAD FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
