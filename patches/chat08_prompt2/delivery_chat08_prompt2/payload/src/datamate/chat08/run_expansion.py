"""Run exact capability evaluation and create controlled Candidate-B children only."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from datamate.chat07_public_candidate import validate_candidate
from datamate.evaluation.capability_eval import evaluate, execute_derived


PARENT_NAME = "wave1_public_revenue_20261030_220018"
PARENT_SHA256 = "0eb7eb9f730bf8f0cbafb8dc3db5fe73b4f75bef99086dfcd5e21591ccf8c66a"
BASELINE_NAME = "chat07_public_20261030_181131"
BASELINE_SHA256 = "c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows), encoding="utf-8")


def _find_submission(root: Path, name: str) -> Path:
    candidates = [root / "artifacts/submissions" / f"submission_{name}.jsonl", root / f"submission_{name}.jsonl"]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f"frozen submission missing: {name}")


def _freeze(root: Path) -> dict[str, str]:
    files = sorted((root / "src/datamate").rglob("*.py")) + sorted((root / "configs").rglob("*.json"))
    return {str(path.relative_to(root)).replace("\\", "/"): _sha(path) for path in files}


def _candidate(root: Path, run_dir: Path, run_id: str, suffix: str,
               families: set[str], enabled: set[str], parent_rows: list[dict], questions: list[dict]) -> dict:
    requested = sorted(families)
    blocked = sorted(families - enabled)
    allowed = families & enabled
    rows = [dict(row) for row in parent_rows]
    by_id = {row["id"]: row for row in rows}
    traces, changed = [], []
    if blocked:
        return {"candidate": suffix, "created": False, "requested_families": requested,
                "blocked_families": blocked, "reason": "train exact/holdout gate failed"}
    for question in questions:
        if question["business_id"] != "dev_002":
            continue
        try:
            record, evidence = execute_derived({**question, "split": "public_test"}, root)
        except Exception as exc:
            traces.append({"id": question["id"], "decision": "abstain", "reason": f"{type(exc).__name__}:{exc}"})
            continue
        if evidence.get("family") not in allowed or record["type"] == "abstain":
            continue
        if by_id[question["id"]]["type"] != "abstain":
            raise ValueError(f"refusing to overwrite parent answer: {question['id']}")
        by_id[question["id"]] = record
        changed.append(question["id"])
        traces.append({"id": question["id"], "decision": "answer", **evidence})
    ordered = [by_id[q["id"]] for q in questions]
    path = root / "artifacts/submissions" / f"submission_{run_id}_{suffix}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(path, ordered)
    validation = validate_candidate(path, root / "public_test/questions.jsonl")
    if not validation["valid"]:
        raise ValueError(f"invalid candidate {suffix}")
    diff = []
    for old, new in zip(parent_rows, ordered, strict=True):
        if old != new:
            diff.append({"id": old["id"], "before": old["type"], "after": new["type"]})
    if {r["id"] for r in diff} != set(changed) or any(r["before"] != "abstain" for r in diff):
        raise ValueError(f"diff gate failed for {suffix}")
    trace_path = run_dir / f"evidence_{suffix}.jsonl"; _write_jsonl(trace_path, traces)
    return {"candidate": suffix, "created": True, "requested_families": requested,
            "changed_ids": changed, "change_count": len(changed),
            "answered_count": sum(r["type"] != "abstain" for r in ordered),
            "path": str(path), "sha256": _sha(path), "validation": validation,
            "diff": diff, "public_accuracy": None}


def run(root: Path, run_id: str, resume: bool = False) -> dict:
    started = time.perf_counter()
    parent = _find_submission(root, PARENT_NAME); baseline = _find_submission(root, BASELINE_NAME)
    if _sha(parent) != PARENT_SHA256 or _sha(baseline) != BASELINE_SHA256:
        raise ValueError("frozen rollback hash mismatch")
    run_dir = root / "artifacts/runs" / run_id; run_dir.mkdir(parents=True, exist_ok=True)
    freeze_before = _freeze(root)
    freeze_path = run_dir / "freeze_manifest.json"
    if freeze_path.exists():
        if json.loads(freeze_path.read_text(encoding="utf-8")) != freeze_before:
            raise ValueError("code/config freeze mismatch; use a new run-id")
    else:
        freeze_path.write_text(json.dumps(freeze_before, ensure_ascii=False, indent=2), encoding="utf-8")
    eval_path = run_dir / "capability_eval.json"
    evaluation = json.loads(eval_path.read_text(encoding="utf-8")) if resume and eval_path.exists() else evaluate(root, run_dir)
    enabled = set(evaluation["public_enabled_families"])
    questions = _jsonl(root / "public_test/questions.jsonl"); parent_rows = _jsonl(parent)
    definitions = {
        "candidate_c_derived_sales": {"average_order_value", "max_revenue_day"},
        "candidate_d_customer": {"customer_spend_ranking"},
        "candidate_e_product": {"product_quantity", "product_ranking"},
        "candidate_f_composed": {"average_order_value", "max_revenue_day", "customer_spend_ranking"},
    }
    candidates = [_candidate(root, run_dir, run_id, suffix, families, enabled, parent_rows, questions)
                  for suffix, families in definitions.items()]
    freeze_after = _freeze(root)
    if freeze_after != freeze_before:
        raise ValueError("code/config changed during run")
    result = {
        "passed": evaluation["passed"], "run_id": run_id,
        "parent": {"name": PARENT_NAME, "path": str(parent), "sha256": _sha(parent), "answered_count": sum(r["type"] != "abstain" for r in parent_rows)},
        "rollback": {"name": BASELINE_NAME, "path": str(baseline), "sha256": _sha(baseline)},
        "evaluation": evaluation, "candidates": candidates,
        "hashes_unchanged_after": _sha(parent) == PARENT_SHA256 and _sha(baseline) == BASELINE_SHA256,
        "code_config_freeze_unchanged": freeze_after == freeze_before,
        "freeze_manifest": str(freeze_path),
        "no_submission_performed": True, "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    (run_dir / "expansion_manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    return 0 if run(args.project_root.resolve(), args.run_id, args.resume)["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
