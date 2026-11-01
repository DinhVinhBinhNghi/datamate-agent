"""Freeze, run, validate and package a reproducible public submission candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from datamate.contracts import SubmissionRecord
from datamate.full_run import run as full_run
from datamate.validate_submission import load_rows, validate_row


VERSION = "wave1-group4-public-v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows, errors = load_rows(path)
    if errors:
        raise ValueError(f"Invalid JSONL {path}: {errors[:3]}")
    return rows


def freeze_snapshot(root: Path, run_id: str, planner: str) -> dict[str, Any]:
    code_root = root / "src/datamate"
    config_root = root / "configs"
    code = {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(code_root.rglob("*.py"))
    }
    configs = {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(config_root.rglob("*.json"))
    }
    return {
        "run_id": run_id,
        "version": VERSION,
        "split": "public_test",
        "planner": planner,
        "model": None,
        "prompt_version": None,
        "threshold": "hard gates only",
        "questions_sha256": _sha256(root / "public_test/questions.jsonl"),
        "rulebook_sha256": _sha256(root / "public_test/rulebook.md"),
        "calendar_sha256": _sha256(root / "public_test/calendar.csv"),
        "code_files_sha256": code,
        "config_files_sha256": configs,
    }


def validate_candidate(submission: Path, questions_path: Path) -> dict[str, Any]:
    raw = submission.read_bytes()
    errors: list[dict[str, Any]] = []
    try:
        text = raw.decode("utf-8")
        utf8_valid = True
    except UnicodeDecodeError as exc:
        text = ""
        utf8_valid = False
        errors.append({"error": "invalid_utf8", "detail": str(exc)})
    rows, parse_errors = load_rows(submission)
    errors.extend(parse_errors)
    expected = _jsonl(questions_path)
    expected_ids = [row["id"] for row in expected]
    actual_ids: list[str] = []
    seen: set[str] = set()
    duplicate_ids: list[str] = []
    for line_no, row in enumerate(rows, 1):
        errors.extend(validate_row(row, line_no))
        try:
            SubmissionRecord.model_validate(row)
        except ValidationError as exc:
            errors.append({"line": line_no, "error": "submission_contract", "detail": str(exc)})
        record_id = row.get("id")
        if isinstance(record_id, str):
            actual_ids.append(record_id)
            if record_id in seen:
                duplicate_ids.append(record_id)
            seen.add(record_id)
    expected_set, actual_set = set(expected_ids), set(actual_ids)
    missing_ids = sorted(expected_set - actual_set)
    extra_ids = sorted(actual_set - expected_set)
    if actual_ids != expected_ids:
        errors.append({"error": "id_order_or_membership_mismatch"})
    type_counts = Counter(row.get("type", "<missing>") for row in rows)
    return {
        "version": VERSION,
        "path": str(submission),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "utf8_valid": utf8_valid,
        "utf8_bom": raw.startswith(b"\xef\xbb\xbf"),
        "ends_with_newline": text.endswith("\n") if utf8_valid else False,
        "expected_question_count": len(expected_ids),
        "row_count": len(rows),
        "type_counts": dict(type_counts),
        "duplicate_ids": sorted(set(duplicate_ids)),
        "missing_ids": missing_ids,
        "extra_ids": extra_ids,
        "errors": errors,
        "valid": (
            utf8_valid and not raw.startswith(b"\xef\xbb\xbf")
            and text.endswith("\n") and len(rows) == len(expected_ids)
            and not errors and not duplicate_ids and not missing_ids and not extra_ids
        ),
        "accuracy": None,
        "note": "Structural and evidence validation only; public answers are unavailable.",
    }


def _evidence_review(predictions: list[dict], traces: list[dict]) -> dict[str, Any]:
    by_operation: dict[str, list[dict]] = defaultdict(list)
    answered = []
    abstain_by_business: dict[str, dict] = {}
    for prediction, trace in zip(predictions, traces):
        if prediction.get("type") != "abstain":
            period = trace.get("period") or {}
            try:
                span = (date.fromisoformat(period["end"]) - date.fromisoformat(period["start"])).days + 1
            except (KeyError, TypeError, ValueError):
                span = None
            item = {
                "id": prediction.get("id"),
                "business_id": trace.get("business_id"),
                "operation": (trace.get("plan") or {}).get("operation"),
                "answer_type": prediction.get("type"),
                "period": period,
                "period_days": span,
                "source_count": len(trace.get("sources") or []),
                "checks": trace.get("checks"),
            }
            answered.append(item)
            by_operation[str(item["operation"])].append(item)
        else:
            abstain_by_business.setdefault(str(trace.get("business_id")), {
                "id": trace.get("id"),
                "business_id": trace.get("business_id"),
                "error_layer": trace.get("error_layer"),
                "reason": trace.get("reason"),
            })
    family_samples = {
        operation: sorted(items, key=lambda item: str(item["id"]))[:3]
        for operation, items in sorted(by_operation.items())
    }
    complexity = sorted(
        answered,
        key=lambda item: (item["period_days"] or -1, item["source_count"], str(item["id"])),
        reverse=True,
    )[:5]
    return {
        "answered_family_samples": family_samples,
        "high_complexity_samples": complexity,
        "unsupported_business_samples": [abstain_by_business[key] for key in sorted(abstain_by_business)[:14]],
        "near_threshold_review": {
            "applicable": False,
            "reason": "No probability threshold; candidate uses deterministic hard gates.",
        },
    }


def _write_public_report(
    path: Path, run_id: str, metrics: dict, validation: dict,
    traces: list[dict], review: dict, freeze: dict,
) -> None:
    decisions = validation["type_counts"]
    layers = Counter((trace.get("error_layer") or "none") for trace in traces)
    operations = Counter(
        (trace.get("plan") or {}).get("operation")
        for trace in traces if trace.get("decision") == "answer"
    )
    lines = [
        f"# Public run report — {run_id}", "",
        f"- Version: `{VERSION}`",
        f"- Questions SHA-256: `{freeze['questions_sha256']}`",
        f"- Submission SHA-256: `{validation['sha256']}`",
        f"- Rows: {validation['row_count']}/{validation['expected_question_count']}",
        f"- Validation: {'PASS' if validation['valid'] else 'FAIL'}",
        f"- Decisions: `{json.dumps(decisions, ensure_ascii=False, sort_keys=True)}`",
        f"- Error layers: `{json.dumps(dict(layers), ensure_ascii=False, sort_keys=True)}`",
        f"- Answered operations: `{json.dumps({str(k): v for k, v in operations.items()}, ensure_ascii=False, sort_keys=True)}`",
        f"- Execution seconds total: {metrics.get('execution_seconds_total')}",
        f"- Planner seconds total: {metrics.get('planner_seconds_total')}",
        "- Public accuracy: not available and not estimated.",
        "- Near-threshold review: not applicable; deterministic hard gates only.", "",
        "## Sanity review", "",
        "Answered samples are recorded by family and complexity in the validation JSON. "
        "Unsupported-business samples confirm fail-closed behavior; they are not answer labels.", "",
        "## Reproduce", "",
        "```powershell",
        "$env:PYTHONPATH='D:\\ZALO\\src'",
        f".\\.venv\\Scripts\\python.exe -m datamate.chat07_public_candidate --project-root D:\\ZALO --run-id {run_id}",
        "```", "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_candidate(root: Path, run_id: str, planner: str = "heuristic") -> dict[str, Any]:
    run_folder = root / "artifacts/runs" / run_id
    run_folder.mkdir(parents=True, exist_ok=True)
    freeze_path = run_folder / "freeze_manifest.json"
    freeze = freeze_snapshot(root, run_id, planner)
    if freeze_path.exists():
        previous = json.loads(freeze_path.read_text(encoding="utf-8"))
        if previous != freeze:
            raise ValueError("freeze manifest mismatch; use a new run_id for changed code/config")
    else:
        freeze_path.write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = full_run(root, "public_test", run_id, planner)
    if freeze_snapshot(root, run_id, planner) != freeze:
        raise ValueError("code/config changed during public run")
    predictions_path = run_folder / "predictions.jsonl"
    evidence_path = run_folder / "evidence.jsonl"
    predictions = _jsonl(predictions_path)
    traces = _jsonl(evidence_path)
    evidence_errors = []
    expected_ids = [row["id"] for row in _jsonl(root / "public_test/questions.jsonl")]
    if len(traces) != len(expected_ids) or [row.get("id") for row in traces] != expected_ids:
        evidence_errors.append({"error": "evidence_id_or_count_mismatch"})
    for index, (prediction, trace) in enumerate(zip(predictions, traces), 1):
        expected_decision = "abstain" if prediction.get("type") == "abstain" else "answer"
        if trace.get("decision") != expected_decision:
            evidence_errors.append({"line": index, "error": "decision_trace_mismatch"})
        if not isinstance(trace.get("reason"), str) and expected_decision == "abstain":
            evidence_errors.append({"line": index, "error": "abstain_without_reason"})

    submissions = root / "artifacts/submissions"
    submissions.mkdir(parents=True, exist_ok=True)
    final_submission = submissions / f"submission_{run_id}.jsonl"
    validation_path = submissions / f"submission_validation_{run_id}.json"
    validation = validate_candidate(predictions_path, root / "public_test/questions.jsonl")
    validation["evidence_errors"] = evidence_errors
    validation["valid"] = validation["valid"] and not evidence_errors
    validation["freeze_manifest"] = str(freeze_path)
    review = _evidence_review(predictions, traces)
    validation["sanity_review"] = review
    if validation["valid"]:
        if final_submission.exists() and final_submission.read_bytes() != predictions_path.read_bytes():
            raise ValueError("existing final submission differs; use a new run_id")
        final_submission.write_bytes(predictions_path.read_bytes())
        validation["path"] = str(final_submission)
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = run_folder / f"public_run_report_{run_id}.md"
    _write_public_report(report_path, run_id, metrics, validation, traces, review, freeze)
    result = {
        "run_id": run_id,
        "valid": validation["valid"],
        "submission": str(final_submission) if validation["valid"] else None,
        "validation_report": str(validation_path),
        "public_run_report": str(report_path),
        "freeze_manifest": str(freeze_path),
        "submission_sha256": validation.get("sha256"),
        "type_counts": validation.get("type_counts"),
        "accuracy": None,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--planner", choices=["heuristic"], default="heuristic")
    args = parser.parse_args()
    result = run_candidate(args.project_root.resolve(), args.run_id, args.planner)
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
