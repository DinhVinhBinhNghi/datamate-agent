from __future__ import annotations

import csv
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from datamate.business.customer_analytics import customer_spend_ranking
from datamate.business.derived_sales import (
    average_order_value, classify_derived, max_revenue_day, revenue_growth,
)
from datamate.business.product_analytics import product_quantity, product_ranking
from datamate.capabilities.sales import default_registry
from datamate.eval.scorer import score
from datamate.format.answer import format_answer
from datamate.load_business import read_config


ANALOGUES = {"biz_102", "biz_103", "biz_104"}
DEVELOPMENT = {"biz_102", "biz_103"}
HOLDOUT = {"biz_104"}
FAMILY_TO_INVENTORY = {
    "average_order_value": "average order value",
    "revenue_growth": "growth/comparison",
    "max_revenue_day": "max/min day",
    "product_quantity": "product quantity",
    "product_ranking": "product ranking",
    "customer_spend_ranking": "customer ranking/loyalty",
}


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def execute_derived(question: dict, root: Path) -> tuple[dict, dict]:
    split, business = question.get("split", "train"), question["business_id"]
    intent = classify_derived(question["question"], question["as_of_date"])
    if intent.family == "unsupported":
        return {"id": question["id"], "type": "abstain"}, {"family": "unsupported"}
    capability = "products" if intent.family.startswith("product_") else "customers" if intent.family.startswith("customer_") else "sales"
    registry = default_registry(root)
    view = registry.build(split, business, capability)
    config = read_config(split, business, root / "configs/businesses")
    if intent.family == "average_order_value":
        answer = average_order_value(view, intent.period)
    elif intent.family == "revenue_growth":
        answer = revenue_growth(view, intent.period, intent.comparison_period)
    elif intent.family == "max_revenue_day":
        answer = max_revenue_day(view, intent.period)
    elif intent.family == "product_quantity":
        answer = product_quantity(view, config, root / split, intent.period, question["question"])
    elif intent.family == "product_ranking":
        answer = product_ranking(view, config, root / split, intent.period, intent.top_k)
    elif intent.family == "customer_spend_ranking":
        answer = customer_spend_ranking(view, intent.period, intent.top_k)
    else:
        return {"id": question["id"], "type": "abstain"}, {"family": intent.family}
    record = format_answer(question["id"], answer, allow_unanswerable=answer["type"] == "unanswerable")
    return record, {"family": intent.family, "capability": capability, "function_evidence": answer.get("evidence", {})}


def evaluate(root: Path, output: Path) -> dict:
    started = time.perf_counter()
    questions = _jsonl(root / "train/questions.jsonl")
    references = {r["id"]: r for r in _jsonl(root / "train/answers.jsonl")}
    inventory_path = root / "artifacts/chat08/family_inventory_train.csv"
    if not inventory_path.exists():
        inventory_path = root / "chat08/family_inventory_train.csv"
    inventory = {r["question_id"]: r for r in csv.DictReader(inventory_path.open(encoding="utf-8-sig"))}
    rows = []
    for question in questions:
        intent = classify_derived(question["question"], question["as_of_date"])
        record = {"id": question["id"], "type": "abstain"}
        error = None
        if question["business_id"] in ANALOGUES and intent.family != "unsupported":
            try:
                record, _ = execute_derived({**question, "split": "train"}, root)
            except Exception as exc:
                error = f"{type(exc).__name__}:{exc}"
        outcome = score(record, references[question["id"]])
        expected_inventory = FAMILY_TO_INVENTORY.get(intent.family)
        inventory_families = set(filter(None, inventory[question["id"]].get("family", "").split("|")))
        inventory_disagreement = bool(
            intent.family != "unsupported"
            and expected_inventory
            and expected_inventory not in inventory_families
        )
        rows.append({
            "id": question["id"], "business_id": question["business_id"],
            "family": intent.family, "prediction_type": record["type"],
            "outcome": outcome, "false_positive": False,
            "inventory_label_disagreement": inventory_disagreement, "error": error,
        })
    family_reports = {}
    enabled = []
    for family in FAMILY_TO_INVENTORY:
        targeted = [r for r in rows if r["family"] == family and r["business_id"] in ANALOGUES]
        dev = [r for r in targeted if r["business_id"] in DEVELOPMENT]
        holdout = [r for r in targeted if r["business_id"] in HOLDOUT]
        report = {
            "target_count": len(targeted), "development_count": len(dev), "holdout_count": len(holdout),
            "correct": sum(r["outcome"] == "correct" for r in targeted),
            "wrong": sum(r["outcome"] == "wrong" for r in targeted),
            "abstain": sum(r["outcome"] == "abstain" for r in targeted),
            "false_positive": sum(r["false_positive"] for r in targeted),
            "inventory_label_disagreement": sum(r["inventory_label_disagreement"] for r in targeted),
            "development_exact": bool(dev) and all(r["outcome"] == "correct" and not r["false_positive"] for r in dev),
            "holdout_exact": bool(holdout) and all(r["outcome"] == "correct" and not r["false_positive"] for r in holdout),
            "question_ids": [r["id"] for r in targeted],
        }
        report["public_enabled"] = report["development_exact"] and report["holdout_exact"] and report["wrong"] == 0 and report["abstain"] == 0 and report["false_positive"] == 0
        if report["public_enabled"]:
            enabled.append(family)
        family_reports[family] = report
    result = {
        "passed": len(rows) == 3000,
        "train_question_count": len(rows),
        "all_outcomes": dict(Counter(r["outcome"] for r in rows)),
        "families": family_reports,
        "public_enabled_families": enabled,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "note": "Only exact development+holdout families are public-enabled; inventory labels are classifier audit evidence, not answer gold.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "capability_eval.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "capability_eval_rows.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    return result
