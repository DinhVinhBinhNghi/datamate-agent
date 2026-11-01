"""Validate train regression, run public, and package the guarded Wave 1 candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from datamate.chat07_public_candidate import (
    VERSION,
    _evidence_review,
    _jsonl,
    freeze_snapshot,
    validate_candidate,
)
from datamate.eval.metrics import summarize
from datamate.eval.scorer import score
from datamate.full_run import run as full_run
from datamate.load_business import read_config
from datamate.planner.direct_revenue import classify_direct_revenue
from datamate.run import process_question


BASELINE_RUN_ID = "chat07_public_20261030_181131"
BASELINE_SHA256 = "c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6"
TRAIN_BUSINESSES = ("biz_102", "biz_103", "biz_104")
TRAIN_TARGET_COUNTS = {"biz_102": 13, "biz_103": 6, "biz_104": 10}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _allowed_public_revenue(question: dict[str, Any]) -> bool:
    if question.get("business_id") != "dev_002":
        return False
    item = classify_direct_revenue(question.get("question", ""))
    period = item.period_expression or ""
    return item.category == "direct_revenue" and (
        period in {"hôm nay", "hôm qua"} or period.startswith("tháng ")
    )


def _metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = summarize(rows)
    result["error_layers"] = dict(
        Counter(row.get("error_layer") or "none" for row in rows)
    )
    result["runtime_seconds"] = round(
        sum(float(row.get("elapsed_seconds", 0)) for row in rows), 3
    )
    return result


def validate_train_regression(root: Path) -> dict[str, Any]:
    questions = _jsonl(root / "train/questions.jsonl")
    references = {
        row["id"]: row for row in _jsonl(root / "train/answers.jsonl")
    }
    target_rows = []
    false_positive = []
    for question in questions:
        if question["business_id"] not in TRAIN_BUSINESSES:
            continue
        classification = classify_direct_revenue(question["question"])
        prediction, evidence = process_question(question, root, "train")
        if classification.category == "direct_revenue":
            target_rows.append({
                "id": question["id"],
                "business_id": question["business_id"],
                "outcome": score(prediction, references[question["id"]]),
                "error_layer": evidence.get("error_layer"),
                "elapsed_seconds": evidence["elapsed_seconds"],
            })
        elif prediction["type"] != "abstain":
            false_positive.append({
                "id": question["id"],
                "business_id": question["business_id"],
                "category": classification.category,
            })
    per_business = {
        business_id: _metric([
            row for row in target_rows if row["business_id"] == business_id
        ])
        for business_id in TRAIN_BUSINESSES
    }
    actual_counts = {
        business_id: per_business[business_id]["total"]
        for business_id in TRAIN_BUSINESSES
    }
    overall = _metric(target_rows)

    biz129_rows = []
    for question in questions:
        if question["business_id"] != "biz_129":
            continue
        prediction, evidence = process_question(question, root, "train")
        biz129_rows.append({
            "outcome": score(prediction, references[question["id"]]),
            "error_layer": evidence.get("error_layer"),
            "elapsed_seconds": evidence["elapsed_seconds"],
        })
    biz129 = _metric(biz129_rows)
    accepted = (
        actual_counts == TRAIN_TARGET_COUNTS
        and overall["total"] == 29
        and overall["correct"] == 29
        and overall["wrong"] == 0
        and overall["abstain"] == 0
        and not false_positive
        and biz129["total"] == 118
        and biz129["correct"] == 7
        and biz129["wrong"] == 0
        and biz129["abstain"] == 111
    )
    return {
        "target_count_expected": TRAIN_TARGET_COUNTS,
        "target_count_actual": actual_counts,
        "per_business": per_business,
        "overall": overall,
        "false_positive_answers_outside_target": false_positive,
        "biz_129": biz129,
        "accepted": accepted,
    }


def compare_to_baseline(
    baseline_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]],
    expected_changed_ids: set[str],
) -> dict[str, Any]:
    if [row.get("id") for row in baseline_rows] != [row.get("id") for row in candidate_rows]:
        return {"passed": False, "reason": "id_order_mismatch"}
    differences = []
    unexpected = []
    for old, new in zip(baseline_rows, candidate_rows, strict=True):
        if old != new:
            item = {
                "id": old["id"], "before": old.get("type"),
                "after": new.get("type"), "answer": new.get("answer"),
            }
            differences.append(item)
            if old["id"] not in expected_changed_ids:
                unexpected.append(item)
    changed_ids = {row["id"] for row in differences}
    missing_expected = sorted(expected_changed_ids - changed_ids)
    shape_ok = all(
        row["before"] == "abstain"
        and row["after"] == "number"
        and type(row["answer"]) is int
        for row in differences
    )
    return {
        "passed": (
            len(expected_changed_ids) == 8
            and len(differences) == 8
            and not unexpected
            and not missing_expected
            and shape_ok
        ),
        "expected_change_count": len(expected_changed_ids),
        "actual_change_count": len(differences),
        "changes": differences,
        "unexpected_changes": unexpected,
        "missing_expected_changes": missing_expected,
        "all_changes_are_abstain_to_integer_number": shape_ok,
    }


def _validate_revenue_evidence(
    questions: list[dict[str, Any]], predictions: list[dict[str, Any]],
    traces: list[dict[str, Any]], expected_ids: set[str],
) -> list[dict[str, Any]]:
    question_by_id = {row["id"]: row for row in questions}
    prediction_by_id = {row["id"]: row for row in predictions}
    trace_by_id = {row["id"]: row for row in traces}
    errors = []
    for question_id in sorted(expected_ids):
        question = question_by_id[question_id]
        prediction = prediction_by_id[question_id]
        trace = trace_by_id[question_id]
        classification = classify_direct_revenue(question["question"])
        plan = trace.get("plan") or {}
        evidence = trace.get("function_evidence") or {}
        checks = trace.get("checks") or {}
        if prediction.get("type") != "number" or type(prediction.get("answer")) is not int:
            errors.append({"id": question_id, "error": "not_integer_number"})
        if (
            trace.get("decision") != "answer"
            or trace.get("error_layer") is not None
            or plan.get("operation") != "revenue"
            or plan.get("business_id") != "dev_002"
            or plan.get("ruleset") != "public_test"
            or plan.get("period") != classification.period_expression
        ):
            errors.append({"id": question_id, "error": "plan_or_decision_mismatch"})
        if not all(checks.get(name) is True for name in (
            "plan_gate", "execution_ok", "evidence_gate", "submission_shape"
        )):
            errors.append({"id": question_id, "error": "gate_check_missing"})
        if (
            evidence.get("business_id") != "dev_002"
            or evidence.get("ruleset") != "public_test"
            or evidence.get("total") != prediction.get("answer")
            or evidence.get("rows_in_period_all_statuses")
            != evidence.get("eligible_rows_after_status_filter", -1)
            + evidence.get("excluded_rows_by_status", -1)
            or evidence.get("distinct_orders_in_period_all_statuses")
            != evidence.get("eligible_distinct_orders", -1)
            + evidence.get("excluded_distinct_orders", -1)
            or not evidence.get("provenance_sources")
            or not evidence.get("source_sheets")
        ):
            errors.append({"id": question_id, "error": "revenue_evidence_mismatch"})
    return errors


def _write_report(path: Path, report: dict[str, Any]) -> None:
    lines = [
        f"# Wave 1 public candidate — {report['run_id']}", "",
        f"- Version: `{VERSION}`",
        f"- Baseline SHA-256 verified: `{report['baseline']['sha256']}`",
        f"- Candidate SHA-256: `{report['candidate']['sha256']}`",
        f"- Submission validation: {'PASS' if report['candidate']['valid'] else 'FAIL'}",
        f"- Train regression: {'PASS' if report['train_regression']['accepted'] else 'FAIL'}",
        f"- Public diff: {'PASS' if report['diff']['passed'] else 'FAIL'}",
        f"- Answered: {report['candidate']['answered_count']}/1000",
        f"- Expected revenue additions: {report['diff'].get('expected_change_count')}",
        f"- Actual changed rows: {report['diff'].get('actual_change_count')}",
        "- Public accuracy: unavailable and not estimated.", "",
        "## Reproduce", "", "```powershell",
        "$env:PYTHONPATH='D:\\ZALO\\src'",
        f".\\.venv\\Scripts\\python.exe -m datamate.wave1_group4_public --project-root D:\\ZALO --run-id {report['run_id']} --baseline D:\\ZALO\\artifacts\\submissions\\submission_{BASELINE_RUN_ID}.jsonl",
        "```", "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(root: Path, run_id: str, baseline_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    if _sha256(baseline_path) != BASELINE_SHA256:
        raise ValueError("Baseline SHA-256 mismatch; refusing to run public candidate")
    baseline_validation = validate_candidate(
        baseline_path, root / "public_test/questions.jsonl"
    )
    if not baseline_validation["valid"]:
        raise ValueError("Frozen baseline is structurally invalid")

    train_regression = validate_train_regression(root)
    if not train_regression["accepted"]:
        raise ValueError("Train exact regression failed; public run is blocked")

    public_questions = _jsonl(root / "public_test/questions.jsonl")
    expected_questions = [q for q in public_questions if _allowed_public_revenue(q)]
    expected_ids = {q["id"] for q in expected_questions}
    if len(expected_ids) != 8:
        raise ValueError(f"Expected exactly 8 public direct-revenue questions, found {len(expected_ids)}")
    config = read_config(
        "public_test", "dev_002", root / "configs/businesses"
    )
    if config.get("monthly_sales", {}).get("revenue_enabled") is not True:
        raise ValueError("Public direct revenue is not enabled in the verified config")

    run_folder = root / "artifacts/runs" / run_id
    run_folder.mkdir(parents=True, exist_ok=True)
    freeze_path = run_folder / "freeze_manifest.json"
    freeze = freeze_snapshot(root, run_id, "heuristic")
    if freeze_path.exists():
        if json.loads(freeze_path.read_text(encoding="utf-8")) != freeze:
            raise ValueError("Freeze manifest mismatch; use a new run_id")
    else:
        freeze_path.write_text(
            json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    metrics = full_run(root, "public_test", run_id, "heuristic")
    if freeze_snapshot(root, run_id, "heuristic") != freeze:
        raise ValueError("Code/config changed during public run")
    predictions_path = run_folder / "predictions.jsonl"
    evidence_path = run_folder / "evidence.jsonl"
    predictions = _jsonl(predictions_path)
    traces = _jsonl(evidence_path)
    structural = validate_candidate(
        predictions_path, root / "public_test/questions.jsonl"
    )
    baseline_rows = _jsonl(baseline_path)
    diff = compare_to_baseline(baseline_rows, predictions, expected_ids)
    evidence_errors = _validate_revenue_evidence(
        public_questions, predictions, traces, expected_ids
    )
    answered_count = sum(row["type"] != "abstain" for row in predictions)
    type_counts = dict(Counter(row["type"] for row in predictions))
    expected_types = {"abstain": 982, "number": 15, "percent": 3}
    review = _evidence_review(predictions, traces)
    accepted = (
        structural["valid"]
        and diff["passed"]
        and not evidence_errors
        and answered_count == 18
        and type_counts == expected_types
        and train_regression["accepted"]
    )

    submissions = root / "artifacts/submissions"
    submissions.mkdir(parents=True, exist_ok=True)
    final_path = submissions / f"submission_{run_id}.jsonl"
    validation_path = submissions / f"submission_validation_{run_id}.json"
    diff_json_path = run_folder / f"public_diff_{run_id}.json"
    report_md_path = run_folder / f"public_run_report_{run_id}.md"
    if accepted:
        if final_path.exists() and final_path.read_bytes() != predictions_path.read_bytes():
            raise ValueError("Existing final submission differs; use a new run_id")
        final_path.write_bytes(predictions_path.read_bytes())
    validation = {
        **structural,
        "path": str(final_path) if accepted else None,
        "valid": accepted,
        "freeze_manifest": str(freeze_path),
        "train_regression": train_regression,
        "diff": diff,
        "revenue_evidence_errors": evidence_errors,
        "sanity_review": review,
        "public_accuracy": None,
    }
    validation_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = {
        "run_id": run_id,
        "version": VERSION,
        "passed": accepted,
        "baseline": {
            "run_id": BASELINE_RUN_ID,
            "path": str(baseline_path),
            "sha256": BASELINE_SHA256,
            "unchanged": _sha256(baseline_path) == BASELINE_SHA256,
        },
        "train_regression": train_regression,
        "public_inventory": {
            "expected_direct_revenue": len(expected_ids),
            "allowed_periods": ["hôm nay", "hôm qua", "tháng M/YYYY"],
        },
        "diff": diff,
        "candidate": {
            "valid": accepted,
            "submission": str(final_path) if accepted else None,
            "validation": str(validation_path),
            "sha256": structural["sha256"],
            "type_counts": type_counts,
            "answered_count": answered_count,
            "accuracy": None,
        },
        "metrics": metrics,
        "revenue_evidence_errors": evidence_errors,
        "freeze_manifest": str(freeze_path),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    diff_json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_report(report_md_path, report)
    report["public_diff_report"] = str(diff_json_path)
    report["public_run_report"] = str(report_md_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    baseline = args.baseline or (
        root / "artifacts/submissions" / f"submission_{BASELINE_RUN_ID}.jsonl"
    )
    result = run(root, args.run_id, baseline.resolve())
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
