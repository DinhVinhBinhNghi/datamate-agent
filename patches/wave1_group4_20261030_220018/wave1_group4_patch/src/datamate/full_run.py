"""Resumable full split run with one evidence packet per question."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from datamate.run import process_question
from datamate.validate_submission import load_rows, validate_row


VERSION = "wave1-group4-public-v1"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root: Path, split: str, run_id: str, planner: str = "heuristic") -> dict:
    if not run_id or not all(c.isalnum() or c in "-_" for c in run_id):
        raise ValueError("run_id must contain only letters, digits, underscore, hyphen")
    question_file = root / split / "questions.jsonl"
    questions = [json.loads(line) for line in question_file.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    ids = [q["id"] for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate question IDs")
    folder = root / "artifacts" / "runs" / run_id
    folder.mkdir(parents=True, exist_ok=True)
    predictions = folder / "predictions.jsonl"
    evidence = folder / "evidence.jsonl"
    manifest_path = folder / "manifest.json"
    identity = {"run_id": run_id, "version": VERSION, "split": split,
                "planner": planner, "questions_sha256": _digest(question_file), "count": len(questions)}
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if any(previous.get(k) != v for k, v in identity.items()):
            raise ValueError("resume manifest/config mismatch")
    else:
        if predictions.exists() or evidence.exists():
            raise ValueError("run files exist without manifest")
        manifest_path.write_text(json.dumps(identity, indent=2), encoding="utf-8")

    old_predictions, p_errors = load_rows(predictions) if predictions.exists() else ([], [])
    old_evidence, e_errors = load_rows(evidence) if evidence.exists() else ([], [])
    if p_errors or e_errors or len(old_predictions) != len(old_evidence):
        raise ValueError("incomplete or invalid checkpoint lines")
    if [row.get("id") for row in old_predictions] != ids[:len(old_predictions)]:
        raise ValueError("checkpoint question order mismatch")
    if [row.get("id") for row in old_evidence] != ids[:len(old_evidence)]:
        raise ValueError("checkpoint evidence order mismatch")

    started = time.perf_counter()
    with predictions.open("a", encoding="utf-8") as pred_out, evidence.open("a", encoding="utf-8") as evidence_out:
        for q in questions[len(old_predictions):]:
            record, packet = process_question(q, root, split, planner)
            if validate_row(record, 1):
                raise ValueError("runner emitted invalid submission row")
            pred_out.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            evidence_out.write(json.dumps(packet, ensure_ascii=False, allow_nan=False) + "\n")
            pred_out.flush()
            evidence_out.flush()

    rows, errors = load_rows(predictions)
    traces, trace_errors = load_rows(evidence)
    errors.extend(trace_errors)
    for i, row in enumerate(rows, 1):
        errors.extend(validate_row(row, i))
    if len(rows) != len(ids) or len(traces) != len(ids) or [r.get("id") for r in rows] != ids:
        errors.append({"error": "missing_or_out_of_order_ids"})
    if errors:
        raise ValueError(f"submission validation failed: {errors[:3]}")

    decisions = Counter(row["type"] for row in rows)
    failures = Counter((trace.get("error_layer") or "none") for trace in traces)
    elapsed = round(time.perf_counter() - started, 3)
    report = {**identity, "decisions": dict(decisions), "error_layers": dict(failures),
              "execution_seconds_total": round(sum(t.get("execution_seconds") or 0 for t in traces), 3),
              "planner_seconds_total": round(sum(t.get("planner_seconds") or 0 for t in traces), 3),
              "elapsed_this_invocation_seconds": elapsed, "valid": True,
              "accuracy": None if split == "public_test" else "evaluate separately against train answers"}
    with (folder / "error_report.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "business_id", "error_layer", "reason"])
        writer.writeheader()
        for t in traces:
            if t["decision"] == "abstain":
                writer.writerow({k: t.get(k) for k in writer.fieldnames})
    (folder / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps({**identity, "completed": True}, indent=2), encoding="utf-8")
    if split == "public_test":
        target = root / "artifacts" / "submissions" / f"candidate_{run_id}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(predictions.read_bytes())
        report["candidate_submission"] = str(target)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--split", choices=["train", "public_test"], required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--planner", choices=["heuristic", "local"], default="heuristic")
    p.add_argument("--project-root", type=Path, default=Path.cwd())
    a = p.parse_args()
    run(a.project_root.resolve(), a.split, a.run_id, a.planner)


if __name__ == "__main__":
    main()
