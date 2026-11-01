from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import pytest

from datamate.readers import SourceLoadError, load_source


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAIN_ROOT = Path(os.environ.get("DATAMATE_TRAIN_ROOT", PROJECT_ROOT / "train"))
CONFIG_ROOT = PROJECT_ROOT / "configs" / "businesses" / "train"


def config_for(business_id: str) -> dict:
    return json.loads((CONFIG_ROOT / f"{business_id}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("business_id", "source_name", "expected_rows", "expected_key", "expected_duplicates"),
    [
        ("biz_129", "orders", 38499, "Số phiếu", 0),
        ("biz_116", "sales_lines", 39889, "Mã đơn hàng", 21790),
        ("biz_123", "orders", 33630, "MaHoaDon", 0),
    ],
)
def test_direct_reader_observed_shape_and_provenance(
    business_id: str,
    source_name: str,
    expected_rows: int,
    expected_key: str,
    expected_duplicates: int,
) -> None:
    config = config_for(business_id)
    source_path = TRAIN_ROOT / config["sources"][source_name]["path"]
    if not source_path.is_file():
        pytest.skip(f"Data source not available: {source_path}")

    frame = load_source(config, source_name, TRAIN_ROOT)

    assert len(frame) == expected_rows
    assert frame[expected_key].isna().sum() == 0
    assert frame[expected_key].dropna().duplicated().sum() == expected_duplicates
    assert {"_source_file", "_source_sheet_or_table", "_source_row"} <= set(frame.columns)
    assert frame["_source_file"].nunique() == 1
    assert frame["_source_sheet_or_table"].nunique() == 1
    assert frame["_source_row"].isna().sum() == 0


def test_csv_raw_values_are_unchanged() -> None:
    config = config_for("biz_129")
    source = config["sources"]["orders"]
    path = TRAIN_ROOT / source["path"]
    if not path.is_file():
        pytest.skip(f"Data source not available: {path}")

    direct = pd.read_csv(path, encoding="utf-8-sig", sep=",", header=0)
    loaded = load_source(config, "orders", TRAIN_ROOT)
    pd.testing.assert_frame_equal(loaded[direct.columns], direct)


def test_sqlite_source_is_not_modified() -> None:
    config = config_for("biz_123")
    path = TRAIN_ROOT / config["sources"]["orders"]["path"]
    if not path.is_file():
        pytest.skip(f"Data source not available: {path}")

    before = hashlib.sha256(path.read_bytes()).hexdigest()
    load_source(config, "orders", TRAIN_ROOT)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert after == before


def test_missing_excel_sheet_fails_with_source_context() -> None:
    config = config_for("biz_116")
    path = TRAIN_ROOT / config["sources"]["sales_lines"]["path"]
    if not path.is_file():
        pytest.skip(f"Data source not available: {path}")
    config["sources"]["sales_lines"]["sheet"] = "sheet_khong_ton_tai"

    with pytest.raises(SourceLoadError, match="sales_lines.*sheet_khong_ton_tai"):
        load_source(config, "sales_lines", TRAIN_ROOT)


def test_missing_sqlite_table_fails_with_source_context() -> None:
    config = config_for("biz_123")
    path = TRAIN_ROOT / config["sources"]["orders"]["path"]
    if not path.is_file():
        pytest.skip(f"Data source not available: {path}")
    config["sources"]["orders"]["table"] = "table_khong_ton_tai"

    with pytest.raises(SourceLoadError, match="orders.*table_khong_ton_tai"):
        load_source(config, "orders", TRAIN_ROOT)
