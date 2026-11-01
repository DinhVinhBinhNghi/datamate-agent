"""Run real-data invariants for the generic monthly sales revenue function."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from datamate.business.monthly_sales_revenue import (
    MonthlySalesRevenueError,
    calculate_monthly_sales_revenue,
)
from datamate.load_business import read_config
from datamate.time.resolve import resolve_period


def _check_result(result: dict) -> dict[str, bool]:
    evidence = result["evidence"]
    return {
        "number_answer": result.get("type") == "number"
        and type(result.get("value")) is int,
        "total_matches_answer": evidence.get("total") == result.get("value"),
        "load_rows_reconcile": evidence["rows_loaded"]
        == evidence["valid_line_rows_before_dedup"]
        + evidence["structural_rows_excluded"],
        "dedup_rows_reconcile": evidence["rows_after_dedup"]
        == evidence["valid_line_rows_before_dedup"]
        - evidence["duplicate_export_rows_removed"],
        "period_rows_reconcile": evidence["rows_in_period_all_statuses"]
        == evidence["eligible_rows_after_status_filter"]
        + evidence["excluded_rows_by_status"],
        "period_orders_reconcile": evidence["distinct_orders_in_period_all_statuses"]
        == evidence["eligible_distinct_orders"]
        + evidence["excluded_distinct_orders"],
        "provenance_present": bool(evidence["source_files"])
        and bool(evidence["source_sheets"]),
        "period_is_inclusive": evidence["period"]["inclusive"] is True,
        "date_basis_declared": evidence["date_basis"] == "Ngày đặt hàng",
        "amount_basis_declared": evidence["amount_column"] == "Tổng tiền",
    }


def run(root: Path, output: Path) -> dict:
    started = time.perf_counter()
    period = resolve_period("tháng 5/2025", "2025-05-31", None, "train")
    businesses = []
    for business_id in ("biz_102", "biz_103", "biz_104"):
        config = read_config("train", business_id, root / "configs/businesses")
        item_started = time.perf_counter()
        result = calculate_monthly_sales_revenue(
            config, root / "train", period, "train"
        )
        checks = _check_result(result)
        businesses.append(
            {
                "business_id": business_id,
                "period": result["evidence"]["period"],
                "result": {"type": result["type"], "value": result["value"]},
                "evidence": result["evidence"],
                "checks": checks,
                "runtime_seconds": round(time.perf_counter() - item_started, 3),
                "passed": all(checks.values()),
                "ground_truth_checked": False,
            }
        )

    public_config = read_config(
        "public_test", "dev_002", root / "configs/businesses"
    )
    public_fail_closed = False
    public_reason = None
    try:
        calculate_monthly_sales_revenue(
            public_config, root / "public_test", period, "public_test"
        )
    except MonthlySalesRevenueError as exc:
        public_reason = str(exc)
        public_fail_closed = "not enabled" in public_reason

    report = {
        "check": "wave1_group2_monthly_sales_revenue",
        "businesses": businesses,
        "public_dev_002_revenue_enabled": public_config["monthly_sales"].get(
            "revenue_enabled"
        ),
        "public_fail_closed": public_fail_closed,
        "public_fail_closed_reason": public_reason,
        "ground_truth_checked": False,
        "note": "Real-data invariant smoke only; exact train-answer scoring belongs to Group 3.",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "passed": all(item["passed"] for item in businesses)
        and public_fail_closed
        and public_config["monthly_sales"].get("revenue_enabled") is False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.project_root.resolve(), args.output.resolve())
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
