import json
from pathlib import Path

from datamate.execution.oracle_plan import run_plans


def test_oracle_fixture_all_four_approved_families_pass():
    root = Path(__file__).resolve().parents[1]
    data_root = root / "train"
    if not (data_root / "data/biz_129/don_hang.csv").is_file():
        data_root = root / "runtime_data/train"
    results = run_plans(
        root / "artifacts/business/oracle_plans_train.jsonl",
        root,
        data_root,
        root / "artifacts/business/oracle_results.jsonl",
    )
    assert len(results) == 4
    assert all(row["status"] == "ok" and row["check_passed"] for row in results)
    assert (root / "artifacts/business/oracle_report.md").is_file()
