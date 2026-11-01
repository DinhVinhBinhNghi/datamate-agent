"""Allowlisted deterministic executor for handwritten JSONL oracle plans."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from datamate.business.cancel import calculate_cancellations
from datamate.business.order_count import calculate_order_count
from datamate.business.revenue import calculate_revenue
from datamate.business.time_operation import resolve_with_evidence
from datamate.business.public_dev002 import calculate_dev002
from datamate.load_business import ConfigError, read_config
from datamate.readers import SourceLoadError
from datamate.time.resolve import PeriodResolutionError


ALLOWED_OPERATIONS = {"resolve_period", "revenue", "order_count", "cancel_rate", "cancel_count"}


def execute_plan(plan: dict[str, Any], project_root: Path, data_root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    plan_id = plan.get("plan_id", "<missing>")
    operation = plan.get("operation")
    base = {
        "plan_id": plan_id,
        "operation": operation,
        "business_id": plan.get("business_id"),
        "ruleset": plan.get("ruleset"),
    }
    try:
        if operation not in ALLOWED_OPERATIONS:
            return {**base, "status": "unsupported", "error_layer": "execution", "reason": f"operation_not_allowed:{operation}"}
        if operation == "resolve_period":
            if plan.get("ruleset") != "train":
                return {**base, "status": "unsupported", "error_layer": "execution", "reason": "public standalone time operation is not enabled"}
            calendar_path = project_root / plan.get("calendar_path", "train/calendar.csv")
            if not calendar_path.is_file():
                calendar_path = data_root / "calendar.csv"
            answer = resolve_with_evidence(
                plan["period"], plan["as_of_date"], calendar_path, "train"
            )
        elif plan.get("ruleset") == "public_test":
            if plan.get("business_id") != "dev_002" or operation not in {"order_count", "cancel_count", "cancel_rate"}:
                return {**base, "status": "unsupported", "error_layer": "execution", "reason": "public capability not enabled"}
            config = read_config("public_test", "dev_002")
            answer = calculate_dev002(
                config, data_root, plan["period"], plan["as_of_date"], operation
            )
        else:
            if plan.get("ruleset") != "train":
                return {**base, "status": "unsupported", "error_layer": "execution", "reason": "unknown ruleset"}
            business_id = plan.get("business_id")
            if business_id != "biz_129":
                return {**base, "status": "unsupported", "error_layer": "execution", "reason": "business_not_supported:train/biz_129 only"}
            config = read_config("train", business_id)
            args = (config, data_root, plan["period"], plan["as_of_date"])
            if operation == "revenue":
                answer = calculate_revenue(*args)
            elif operation == "order_count":
                answer = calculate_order_count(*args)
            else:
                answer = calculate_cancellations(*args)
    except (ConfigError, SourceLoadError, OSError) as exc:
        return {**base, "status": "error", "error_layer": "loader", "reason": str(exc), "runtime_seconds": round(time.perf_counter() - started, 6)}
    except (KeyError, TypeError, ValueError, PeriodResolutionError) as exc:
        return {**base, "status": "error", "error_layer": "execution", "reason": str(exc), "runtime_seconds": round(time.perf_counter() - started, 6)}

    runtime = round(time.perf_counter() - started, 6)
    try:
        serialized = json.loads(json.dumps(answer, ensure_ascii=False, allow_nan=False))
        check = plan.get("expected_value")
        actual = serialized.get("value") if serialized.get("type") != "date_range" else serialized.get("value")
        result = {**base, "status": "ok", "error_layer": None, "answer": serialized, "runtime_seconds": runtime}
        if check is not None:
            result["expected_value"] = check
            result["check_passed"] = actual == check
        return result
    except (TypeError, ValueError) as exc:
        return {**base, "status": "error", "error_layer": "formatter", "reason": str(exc), "runtime_seconds": runtime}


def run_plans(plans_path: Path, project_root: Path, data_root: Path, output_path: Path) -> list[dict[str, Any]]:
    plans = [json.loads(line) for line in plans_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = [execute_plan(plan, project_root, data_root) for plan in plans]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results), encoding="utf-8")
    report_path = output_path.with_name("oracle_report.md")
    ok = sum(row.get("status") == "ok" and row.get("check_passed", True) for row in results)
    unsupported = sum(row.get("status") == "unsupported" for row in results)
    errors = [row for row in results if row.get("status") == "error"]
    report_lines = [
        "# Oracle execution report",
        "",
        f"- Plans: {len(results)}",
        f"- Successful checks: {ok}",
        f"- Unsupported: {unsupported}",
        f"- Errors: {len(errors)}",
        "- Error layers: " + (", ".join(f"{layer}={sum(r.get('error_layer') == layer for r in errors)}" for layer in ("loader", "execution", "formatter")) if errors else "none"),
        "",
        "| Plan | Operation | Status | Runtime (s) | Check | Reason |",
        "|---|---|---|---:|---|---|",
    ]
    for row in results:
        report_lines.append(
            f"| {row.get('plan_id')} | {row.get('operation')} | {row.get('status')} | "
            f"{row.get('runtime_seconds', '')} | {row.get('check_passed', '')} | {row.get('reason', '')} |"
        )
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plans", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, default=Path.cwd() / "train")
    parser.add_argument("--output", type=Path, default=Path("artifacts") / "business" / "oracle_results.jsonl")
    args = parser.parse_args(argv)
    try:
        results = run_plans(args.plans, args.project_root, args.data_root, args.output)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ORACLE FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"plan_count": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
