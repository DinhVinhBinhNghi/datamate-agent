"""Evaluate planner decisions against handwritten development intent labels, without execution."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from datamate.benchmark_planner import percentile
from datamate.plan_question import lookup_question, run_question
from datamate.planner.validate import PlannerFailure, validate_query_plan


def category(row: dict, label: dict) -> str | None:
    if row["status"] == "planner_failure":
        reason = row.get("reason", "")
        if label["supported"]:
            if "period" in reason:
                return "period"
            if "schema" in reason:
                return "schema"
            return "intent"
        return "unsupported"  # correct rejection, still tracked by reason below
    if not label["supported"]:
        return "unsupported"
    intent = row["intent"]
    if intent["family"] != label["family"] or row["plan"]["operation"] != label["operation"]:
        return "intent"
    if intent["period_expression"] != label["period"]:
        return "period"
    if intent["answer_type"] != label["answer_type"]:
        return "schema"
    if intent["entity_filter"] is not None or intent["grouping"] is not None:
        return "entity/filter"
    return None


def evaluate(root: Path, labels_path: Path, output: Path, report: Path) -> dict:
    labels = [json.loads(line) for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [r["question_id"] for r in labels]
    if len(ids) != len(set(ids)) or not labels:
        raise ValueError("Oracle intent labels must have distinct question IDs")
    rows = []
    for label in labels:
        question = lookup_question(root / "train/questions.jsonl", label["question_id"])
        result = run_question(question, root, execute=False)
        result["oracle_label"] = label
        result["failure_category"] = category(result, label)
        if result["status"] == "planned":
            try:
                validate_query_plan(result["plan"], question, root)
                result["schema_pass"] = True
            except PlannerFailure:
                result["schema_pass"] = False
        else:
            result["schema_pass"] = False
        rows.append(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    supported = [r for r in rows if r["oracle_label"]["supported"]]
    unsupported = [r for r in rows if not r["oracle_label"]["supported"]]
    planned = [r for r in rows if r["status"] == "planned"]
    supported_planned = [r for r in supported if r["status"] == "planned"]
    summary = {
        "development_total": len(rows), "hand_labeled_supported": len(supported),
        "hand_labeled_unsupported": len(unsupported),
        "heuristic_planned": len(planned),
        "heuristic_json_valid": f"{len(planned)}/{len(planned)}" if planned else "0/0",
        "heuristic_schema_pass": f"{sum(r['schema_pass'] for r in planned)}/{len(planned)}" if planned else "0/0",
        "supported_family_correct": f"{sum(r['intent']['family'] == r['oracle_label']['family'] for r in supported_planned)}/{len(supported)}",
        "supported_period_correct": f"{sum(r['intent']['period_expression'] == r['oracle_label']['period'] for r in supported_planned)}/{len(supported)}",
        "supported_type_correct": f"{sum(r['intent']['answer_type'] == r['oracle_label']['answer_type'] for r in supported_planned)}/{len(supported)}",
        "unsupported_detected": f"{sum(r['status'] == 'planner_failure' for r in unsupported)}/{len(unsupported)}",
        "planner_latency_p50_seconds": percentile([r["planner_seconds"] for r in rows], .5),
        "planner_latency_p95_seconds": percentile([r["planner_seconds"] for r in rows], .95),
        "heuristic_retries": 0, "heuristic_timeouts": 0,
        "model_json_valid": None, "model_accuracy": None, "model_latency": None,
        "default_planner": "heuristic", "execution_run": False,
    }
    counts = Counter(r["failure_category"] for r in rows if r["failure_category"] is not None)
    report_lines = ["# Planner evaluation — Chat 5 Nhóm 4", "",
                    "Development questions only; 10 intent labels were written by hand from the question text and Chat 4 allowlist. This is a deliberately selected set, not a representative or held-out estimate of 3,000 questions.",
                    "", "```json", json.dumps(summary, ensure_ascii=False, indent=2), "```", "",
                    "| Question ID | Oracle supported | Planner | Family | Period | Category |", "|---|---|---|---|---|---|"]
    for row in rows:
        intent = row.get("intent", {})
        report_lines.append(f'| {row["question_id"]} | {row["oracle_label"]["supported"]} | {row["status"]} | {intent.get("family", "")} | {intent.get("period_expression", "")} | {row["failure_category"] or ""} |')
    report_lines += ["", "Rejection categories (correct unsupported detection included): " + json.dumps(dict(counts), ensure_ascii=False),
                     "", "Error taxonomy: intent, period, entity/filter, unsupported, schema, latency. Categories not observed in this selected set have count 0; no model latency was measured.",
                     "", "Comparison: heuristic measured; local model unavailable. Keep heuristic as default. Model path remains optional backlog until an installed model shows better coverage/accuracy at acceptable latency and schema pass rate.",
                     "", "No train answers were put in a runtime prompt; no public test labels were used. Executor outcomes are intentionally excluded from planner metrics."]
    report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()
    summary = evaluate(root, root / "tests/planner/fixtures/oracle_intents_dev.jsonl",
                       root / "artifacts/planner/planner_eval_results.jsonl",
                       root / "artifacts/planner/planner_report.md")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
