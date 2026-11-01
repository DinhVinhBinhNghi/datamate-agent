"""Acceptance check for the single Chat 07 Group 2 experiment."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from datamate.eval.metrics import summarize
from datamate.eval.scorer import score
from datamate.run import process_question


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def run(root: Path, output: Path) -> dict:
    train_questions = _jsonl(root / "train/questions.jsonl")
    references = {row["id"]: row for row in _jsonl(root / "train/answers.jsonl")}
    train_rows = []
    started = time.perf_counter()
    for question in train_questions:
        if question["business_id"] != "biz_129":
            continue
        prediction, evidence = process_question(question, root, "train")
        train_rows.append({
            "id": question["id"],
            "outcome": score(prediction, references[question["id"]]),
            "decision": evidence["decision"],
            "error_layer": evidence.get("error_layer"),
            "operation": (evidence.get("plan") or {}).get("operation"),
        })
    train_metrics = summarize(train_rows)
    train_metrics["error_layers"] = dict(Counter(row["error_layer"] or "none" for row in train_rows))

    public_questions = [
        question for question in _jsonl(root / "public_test/questions.jsonl")
        if question["business_id"] == "dev_002"
    ]
    answered = []
    public_layers = Counter()
    for question in public_questions:
        prediction, evidence = process_question(question, root, "public_test")
        public_layers[evidence.get("error_layer") or "none"] += 1
        if prediction["type"] != "abstain":
            answered.append({
                "id": question["id"],
                "operation": evidence["plan"]["operation"],
                "type": prediction["type"],
            })
    public_smoke = {
        "total": len(public_questions),
        "answers": len(answered),
        "abstain": len(public_questions) - len(answered),
        "error_layers": dict(public_layers),
        "answered": answered,
        "accuracy": None,
    }
    train_pass = (
        train_metrics["total"] == 118 and train_metrics["correct"] == 7
        and train_metrics["wrong"] == 0 and train_metrics["abstain"] == 111
    )
    public_pass = (
        public_smoke["total"] == 41 and public_smoke["answers"] == 10
        and public_layers == Counter({"planner": 31, "none": 10})
    )
    report = {
        "experiment": "public_test/dev_002 order_count+cancel only",
        "version": "chat07-group2-dev002-v1",
        "train_biz_129": train_metrics,
        "public_dev_002_smoke": public_smoke,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "accepted": train_pass and public_pass,
        "acceptance": {"train_regression_pass": train_pass, "public_smoke_pass": public_pass},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output", type=Path,
        default=Path("artifacts/experiments/chat07_group2_windows_check.json"),
    )
    args = parser.parse_args()
    report = run(args.project_root.resolve(), args.output.resolve())
    return 0 if report["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
