from pathlib import Path

import pandas as pd

from datamate.audit_monthly_sales import parse_vnd
from datamate.readers import load_source


def test_xlsx_sheets_reads_matching_sheets_and_forward_fills_per_sheet(tmp_path: Path):
    path = tmp_path / "orders.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"order": ["A", None], "amount": [10, 20]}).to_excel(
            writer, sheet_name="01.2025", index=False
        )
        pd.DataFrame({"order": ["B"], "amount": [30]}).to_excel(
            writer, sheet_name="02.2025", index=False
        )
        pd.DataFrame({"ignored": [1]}).to_excel(
            writer, sheet_name="Notes", index=False
        )
    config = {
        "sources": {"orders": {
            "format": "xlsx_sheets",
            "path": "orders.xlsx",
            "sheet_pattern": r"^[0-9]{2}\.[0-9]{4}$",
            "expected_sheets": 2,
            "header_row": 0,
            "forward_fill_columns": ["order"],
            "semantic_columns": {"order_id": "order", "line_amount": "amount"},
        }}
    }
    result = load_source(config, "orders", tmp_path)
    assert result["order"].tolist() == ["A", "A", "B"]
    assert result["_source_sheet_or_table"].tolist() == [
        "01.2025", "01.2025", "02.2025"
    ]


def test_parse_vnd_accepts_verified_archetype_formats_and_rejects_ambiguity():
    assert parse_vnd("38,000") == 38000
    assert parse_vnd("10.000đ") == 10000
    assert parse_vnd("105k") == 105000
    assert parse_vnd(25000) == 25000
    assert parse_vnd("not money") is None
    assert parse_vnd("1.5") is None
