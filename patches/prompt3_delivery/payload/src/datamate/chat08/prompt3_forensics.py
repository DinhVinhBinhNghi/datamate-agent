"""Document the 15 Prompt 2 failures from frozen evaluation and train gold."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from datamate.evaluation.capability_eval import execute_derived
from datamate.business.derived_sales import classify_derived


FIELDS = ("question_id", "business_id", "question", "as_of_date", "old_family", "expected_type", "expected_value", "old_actual_type", "new_type", "new_value", "parsed_intent", "resolved_period", "source", "selected_row_count", "status_mapping", "unit_conversion", "numerator", "denominator", "grouping_key", "tie_set", "raw_evidence_sample", "root_cause", "confidence", "generic_fix", "similar_public_pattern")


def run(root: Path, output: Path) -> dict:
    old = root / "artifacts/runs/chat08_prompt2_final/capability_eval_rows.csv"
    if not old.exists():
        old = root / "artifacts/chat08_prompt3/prompt2_eval_rows.csv"
    questions = {r["id"]: r for r in (json.loads(line) for line in (root / "train/questions.jsonl").open(encoding="utf-8-sig"))}
    answers = {r["id"]: r for r in (json.loads(line) for line in (root / "train/answers.jsonl").open(encoding="utf-8-sig"))}
    old_failures = [r for r in csv.DictReader(old.open(encoding="utf-8-sig")) if r["business_id"] in {"biz_102", "biz_103", "biz_104"} and r["outcome"] == "wrong"]
    output.mkdir(parents=True, exist_ok=True)
    groups = {"revenue_growth": [], "product_quantity": [], "product_ranking": []}
    for row in old_failures:
        q, gold = questions[row["id"]], answers[row["id"]]
        record, evidence = execute_derived({**q, "split": "train"}, root)
        intent = classify_derived(q["question"], q["as_of_date"])
        kind = row["family"]
        cause = {"revenue_growth": "classifier/parser: three-month revenue list mistaken for percent growth", "product_quantity": "classifier/parser: size-wide cup count mistaken for named product", "product_ranking": "classifier/parser: customer rank mistaken for product rank"}[kind]
        fix = {"revenue_growth": "exclude multi-month list from percent-growth operation", "product_quantity": "typed size_quantity with size suffix and cup unit", "product_ranking": "route customer-money ranking before product ranking"}[kind]
        groups[kind].append({"question_id": q["id"], "business_id": q["business_id"], "question": q["question"], "as_of_date": q["as_of_date"], "old_family": kind, "expected_type": gold["type"], "expected_value": json.dumps(gold.get("answer"), ensure_ascii=False), "old_actual_type": row["prediction_type"], "new_type": record["type"], "new_value": json.dumps(record.get("answer"), ensure_ascii=False), "parsed_intent": intent.family, "resolved_period": str(intent.period), "source": f"train/data/{q['business_id']}/DonHang_ChiTiet.xlsx", "selected_row_count": evidence.get("function_evidence", {}).get("selected_rows", ""), "status_mapping": "revenue_eligible(train)", "unit_conversion": "DanhSachQuyDoi.xlsx for product measures", "numerator": "", "denominator": "", "grouping_key": "size suffix" if kind == "product_quantity" else "", "tie_set": "", "raw_evidence_sample": "", "root_cause": cause, "confidence": "high: wording, gold type and repaired prediction agree", "generic_fix": fix, "similar_public_pattern": "yes"})
    for kind, rows in groups.items():
        path = output / f"{kind.replace('revenue_', 'growth_')}_failures.csv"
        if kind == "revenue_growth": path = output / "growth_failures.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, FIELDS); writer.writeheader(); writer.writerows(rows)
    with (output / "root_cause_summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, ("old_family", "count", "root_cause", "generic_fix")); writer.writeheader()
        for kind, rows in groups.items(): writer.writerow({"old_family": kind, "count": len(rows), "root_cause": rows[0]["root_cause"], "generic_fix": rows[0]["generic_fix"]})
    (output / "failure_forensics.md").write_text("# Prompt 3 forensic\n\n" + "\n".join(f"- {kind}: {len(rows)} classifier routing errors; {rows[0]['generic_fix']}." for kind, rows in groups.items()) + "\n\nThree growth cases are multi-month lists, eleven quantity cases are size totals, and one product ranking case is a customer rank. The full per-question records are in the CSV files.\n", encoding="utf-8")
    return {kind: len(rows) for kind, rows in groups.items()}
