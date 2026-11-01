"""Exact train validation for Wave 1 direct revenue; public stays disabled."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from pathlib import Path

from datamate.chat07_group2_check import run as run_baseline_regression
from datamate.eval.metrics import summarize
from datamate.eval.scorer import score
from datamate.load_business import read_config
from datamate.planner.direct_revenue import classify_direct_revenue
from datamate.run import process_question


BUSINESSES = ("biz_102", "biz_103", "biz_104")
EXPECTED_TARGET_COUNTS = {"biz_102": 13, "biz_103": 6, "biz_104": 10}


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _metrics(rows: list[dict]) -> dict:
    result = summarize(rows)
    result["error_layers"] = dict(
        Counter(row.get("error_layer") or "none" for row in rows)
    )
    result["runtime_seconds"] = round(
        sum(float(row.get("elapsed_seconds", 0)) for row in rows), 3
    )
    return result


def run(root: Path, output_dir: Path) -> dict:
    started = time.perf_counter()
    questions = _jsonl(root / "train/questions.jsonl")
    references = {
        row["id"]: row for row in _jsonl(root / "train/answers.jsonl")
    }
    if len(questions) != len(references):
        raise ValueError("Train question/answer inventory mismatch")

    inventory = []
    target_rows = []
    false_positive_answers = []
    by_business_wall = {}
    for business_id in BUSINESSES:
        business_started = time.perf_counter()
        for question in questions:
            if question["business_id"] != business_id:
                continue
            classification = classify_direct_revenue(question["question"])
            reference = references[question["id"]]
            inventory.append({
                "id": question["id"],
                "business_id": business_id,
                "as_of_date": question["as_of_date"],
                "category": classification.category,
                "period_expression": classification.period_expression or "",
                "reference_type": reference["type"],
                "question": question["question"],
            })
            prediction, evidence = process_question(question, root, "train")
            is_target = classification.category == "direct_revenue"
            if is_target:
                target_rows.append({
                    "id": question["id"],
                    "business_id": business_id,
                    "question": question["question"],
                    "period_expression": classification.period_expression,
                    "prediction": prediction,
                    "reference": reference,
                    "outcome": score(prediction, reference),
                    "decision": evidence["decision"],
                    "error_layer": evidence.get("error_layer"),
                    "reason": evidence.get("reason"),
                    "elapsed_seconds": evidence["elapsed_seconds"],
                    "function_evidence": evidence.get("function_evidence"),
                })
            elif prediction["type"] != "abstain":
                false_positive_answers.append({
                    "id": question["id"],
                    "business_id": business_id,
                    "category": classification.category,
                    "question": question["question"],
                    "prediction": prediction,
                })
        by_business_wall[business_id] = round(
            time.perf_counter() - business_started, 3
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = output_dir / "wave1_group3_family_inventory.csv"
    with inventory_path.open("w", encoding="utf-8-sig", newline="") as sink:
        writer = csv.DictWriter(sink, fieldnames=list(inventory[0]))
        writer.writeheader()
        writer.writerows(inventory)
    results_path = output_dir / "wave1_group3_target_results.jsonl"
    results_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n"
            for row in target_rows
        ),
        encoding="utf-8",
    )

    per_business = {}
    for business_id in BUSINESSES:
        rows = [row for row in target_rows if row["business_id"] == business_id]
        per_business[business_id] = _metrics(rows)
        per_business[business_id]["wall_seconds"] = by_business_wall[business_id]
    overall = _metrics(target_rows)
    category_counts = {
        business_id: dict(
            sorted(Counter(
                item["category"] for item in inventory
                if item["business_id"] == business_id
            ).items())
        )
        for business_id in BUSINESSES
    }

    public_questions = [
        question for question in _jsonl(root / "public_test/questions.jsonl")
        if question["business_id"] == "dev_002"
        and classify_direct_revenue(question["question"]).category == "direct_revenue"
    ]
    public_lock_rows = []
    for question in public_questions:
        prediction, evidence = process_question(question, root, "public_test")
        public_lock_rows.append({
            "id": question["id"],
            "period_expression": classify_direct_revenue(
                question["question"]
            ).period_expression,
            "prediction_type": prediction["type"],
            "error_layer": evidence.get("error_layer"),
        })
    public_config = read_config(
        "public_test", "dev_002", root / "configs/businesses"
    )
    public_locked = (
        len(public_lock_rows) == 8
        and all(row["prediction_type"] == "abstain" for row in public_lock_rows)
        and public_config["monthly_sales"].get("revenue_enabled") is False
    )

    baseline_path = output_dir / "wave1_group3_baseline_regression.json"
    baseline = run_baseline_regression(root, baseline_path)
    target_counts = Counter(row["business_id"] for row in target_rows)
    counts_match = dict(target_counts) == EXPECTED_TARGET_COUNTS
    exact_pass = (
        overall["total"] == sum(EXPECTED_TARGET_COUNTS.values())
        and overall["correct"] == overall["total"]
        and overall["wrong"] == 0
        and overall["abstain"] == 0
    )
    accepted = (
        counts_match
        and exact_pass
        and not false_positive_answers
        and public_locked
        and baseline["accepted"]
    )
    report = {
        "version": "wave1-group3-train-exact-v1",
        "scope": "direct shop-wide revenue for one resolved period only",
        "target_count_expected": EXPECTED_TARGET_COUNTS,
        "target_count_actual": dict(target_counts),
        "category_counts": category_counts,
        "per_business": per_business,
        "overall": overall,
        "false_positive_answers_outside_target": false_positive_answers,
        "public_dev_002": {
            "direct_revenue_inventory": len(public_lock_rows),
            "revenue_enabled": public_config["monthly_sales"].get(
                "revenue_enabled"
            ),
            "all_eight_still_abstain": public_locked,
            "rows": public_lock_rows,
            "accuracy": None,
        },
        "baseline_regression": {
            "accepted": baseline["accepted"],
            "train_biz_129": baseline["train_biz_129"],
            "public_dev_002_answers": baseline["public_dev_002_smoke"]["answers"],
        },
        "artifacts": {
            "inventory": str(inventory_path),
            "target_results": str(results_path),
            "baseline_regression": str(baseline_path),
        },
        "ground_truth_checked": True,
        "public_accuracy": None,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "accepted": accepted,
    }
    report_path = output_dir / "wave1_group3_train_validation.json"
    report["artifacts"]["report"] = str(report_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    markdown_path = output_dir / "wave1_group3_train_validation.md"
    lines = [
        "# Wave 1 Group 3 — train exact validation",
        "",
        "Scope: direct shop-wide revenue for exactly one resolved period. Growth, "
        "average order, ranking/threshold, entity-specific, and multi-period questions "
        "remain abstain.",
        "",
        "| Business | Target | Correct | Wrong | Abstain | Score | Runtime (s) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for business_id in BUSINESSES:
        item = per_business[business_id]
        lines.append(
            f"| {business_id} | {item['total']} | {item['correct']} | "
            f"{item['wrong']} | {item['abstain']} | {item['score']} | "
            f"{item['wall_seconds']} |"
        )
    lines.extend([
        "",
        f"- Exact target pass: {exact_pass}",
        f"- Answers outside target: {len(false_positive_answers)}",
        f"- Public eight-pattern inventory still locked: {public_locked}",
        f"- Baseline regression accepted: {baseline['accepted']}",
        f"- Overall accepted: {accepted}",
    ])
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report["artifacts"]["markdown"] = str(markdown_path)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("artifacts/eval/wave1_group3"),
    )
    args = parser.parse_args()
    report = run(args.project_root.resolve(), args.output_dir.resolve())
    return 0 if report["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
