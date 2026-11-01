from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from .inventory import write_csv


BASELINE_ANSWERED_IDS = {
    "q_03bbdfa6e0d5", "q_0ac818a0f5f2", "q_0c62d2078959", "q_585664a97754",
    "q_5896bf2cce00", "q_663c209f7209", "q_9b5377726889", "q_c2ba3823e50f",
    "q_e6c703f05070", "q_e76cb855b50c",
}

WAVE1_ADDED_IDS = {
    "q_00bf8df3ea0b", "q_1f1a1f45b377", "q_61cfc26159fa", "q_7616f1a1f0ee",
    "q_c120861e5dd1", "q_dbb084b9361d", "q_f4e0630ebcb1", "q_fe5788dae82e",
}

SALES_CORE = {
    "direct revenue", "order count", "cancel count/rate", "average order value",
    "growth/comparison", "max/min day", "revenue share",
}

EXPANSION_C = {
    "product quantity", "product ranking", "customer ranking/loyalty",
    "payment/debt", "inventory", "purchase", "COGS/profit", "industry-specific",
}


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def analogue_businesses(matrix_row: dict) -> list[str]:
    return re.findall(r"\b(?:biz_\d{3})\b", matrix_row.get("train_analogues", ""))


def linked_train_ids(train: list[dict], business_ids: list[str], families: set[str]) -> list[str]:
    return [
        row["question_id"] for row in train
        if row["business_id"] in set(business_ids) and row["primary_family"] in families
    ]


def bucket_row(
    bucket_id: str,
    option: str,
    scope: str,
    public_rows: list[dict],
    families: set[str],
    train: list[dict],
    analogues: list[str],
    exactness: int,
    transfer: int,
    effort: int,
    risk: int,
    evidence: str,
    blocker: str,
    decision: str = "not_selected",
) -> dict:
    ids = [r["question_id"] for r in public_rows]
    train_ids = linked_train_ids(train, analogues, families)
    score = round(len(ids) * exactness * transfer / (effort * risk), 3) if effort and risk else 0
    return {
        "bucket_id": bucket_id,
        "option": option,
        "scope": scope,
        "families": "|".join(sorted(families)),
        "question_count": len(ids),
        "expected_upside_ceiling": len(ids),
        "train_exactness_ordinal_1_to_3": exactness,
        "transfer_evidence_ordinal_1_to_3": transfer,
        "implementation_effort_ordinal_1_to_5": effort,
        "semantic_risk_ordinal_1_to_5": risk,
        "ordinal_priority_score": score,
        "evidence": evidence,
        "blocker": blocker,
        "train_analogue_businesses": "|".join(analogues),
        "public_question_ids": "|".join(ids),
        "train_analogue_question_ids": "|".join(train_ids),
        "decision": decision,
    }


def run(output_dir: Path) -> dict:
    train = read_csv(output_dir / "family_inventory_train.csv")
    public = read_csv(output_dir / "family_inventory_public.csv")
    matrix = read_csv(output_dir / "business_archetype_matrix.csv")
    matrix_by_business = {r["business_id"]: r for r in matrix}
    rows = []

    dev002_all = [r for r in public if r["business_id"] == "dev_002"]
    answered = BASELINE_ANSWERED_IDS | WAVE1_ADDED_IDS
    dev002_remaining = [r for r in dev002_all if r["question_id"] not in answered]
    rows.append(bucket_row(
        "A_dev002_remaining_23", "A", "finish the 23 unanswered dev_002 questions",
        dev002_remaining, {r["primary_family"] for r in dev002_remaining}, train,
        ["biz_102", "biz_103", "biz_104"], 2, 3, 2, 2,
        "same public adapter already enabled; Wave1 exact direct-revenue validation 29/29; new metrics themselves are not yet exact-validated",
        "must add per-family exact train oracles for AOV/growth/product/customer/ranking before public enablement",
        "PRIMARY",
    ))

    for family in sorted({r["primary_family"] for r in dev002_remaining}):
        subset = [r for r in dev002_remaining if r["primary_family"] == family]
        rows.append(bucket_row(
            "A_dev002_" + re.sub(r"[^a-z0-9]+", "_", family.lower()).strip("_"),
            "A", f"dev_002 remaining: {family}", subset, {family}, train,
            ["biz_102", "biz_103", "biz_104"],
            2 if family in {"average order value", "growth/comparison", "max/min day"} else 1,
            3, 2 if family in SALES_CORE else 3, 2 if family in SALES_CORE else 3,
            "same dev_002 source adapter; family classification is rule-based inventory, not gold",
            "family-specific semantics and exact train validation missing",
        ))

    # Option B is intentionally split per business; one all-public score would
    # hide schema and semantic differences.
    for business_id in sorted({r["business_id"] for r in public if r["business_id"] != "dev_002"}):
        subset = [r for r in public if r["business_id"] == business_id and r["primary_family"] in SALES_CORE]
        analogues = analogue_businesses(matrix_by_business[business_id])[:3]
        mechanical = matrix_by_business[business_id].get("train_analogues", "")
        transfer = 2 if re.search(r":0\.(?:9|8)", mechanical) else 1
        source_count = int(matrix_by_business[business_id].get("source_file_count", 0) or 0)
        table_count = int(matrix_by_business[business_id].get("table_count", 0) or 0)
        archetype = matrix_by_business[business_id].get("format_archetype", "")
        if source_count > 10 or table_count > 20:
            effort, risk = 5, 4
        elif "fragmented_excel" in archetype or source_count > 5:
            effort, risk = 4, 4
        else:
            effort, risk = 3, 3
        decision = "SECONDARY" if business_id == "dev_006" else "not_selected"
        rows.append(bucket_row(
            f"B_{business_id}_sales_core", "B", f"sales core on {business_id}", subset,
            SALES_CORE, train, analogues, 2, transfer, effort, risk,
            f"mechanical archetype/header analogues: {mechanical}; direct-revenue logic has 29/29 Wave1 exact evidence on another archetype",
            "README semantics, grain/cardinality, source coverage and train exact adapter validation required",
            decision,
        ))

    c_rows = [r for r in public if r["primary_family"] in EXPANSION_C]
    all_analogues = sorted({b for row in matrix if row["split"] == "public_test" for b in analogue_businesses(row)})
    rows.append(bucket_row(
        "C_product_customer_debt_inventory", "C", "cross-public product/customer/debt/inventory expansion",
        c_rows, EXPANSION_C, train, all_analogues, 1, 1, 5, 5,
        "large measured question pool, but current evidence is candidate-level and highly heterogeneous",
        "unit conversion, customer identity, debt snapshots, purchase/inventory flow, COGS and industry rules need separate adapters",
        "STRETCH",
    ))

    c6 = [r for r in public if r["business_id"] == "dev_006" and r["primary_family"] in EXPANSION_C]
    rows.append(bucket_row(
        "C_dev006_relational_extensions", "C", "dev_006 product/customer/debt/inventory on relational SQLite",
        c6, EXPANSION_C, train, ["biz_123"], 1, 2, 4, 5,
        "dev_006 mechanical schema similarity to biz_123=0.9554; biz_123 join cardinality was verified in Chat03",
        "business semantics beyond the verified order-detail join are not exact-validated",
        "STRETCH_PILOT",
    ))

    write_csv(output_dir / "priority_buckets.csv", rows)
    decisions = {r["decision"]: r["bucket_id"] for r in rows if r["decision"] != "not_selected"}
    result = {
        "bucket_count": len(rows),
        "dev002_total": len(dev002_all),
        "baseline_answered_ids": len(BASELINE_ANSWERED_IDS),
        "wave1_added_ids": len(WAVE1_ADDED_IDS),
        "dev002_remaining": len(dev002_remaining),
        "decisions": decisions,
        "ordinal_scale_note": "question_count measured; exactness/transfer 1=low,2=medium,3=high; effort/risk 1=low to 5=high; scores rank only within this audit",
    }
    (output_dir / "priority_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build evidence-linked DataMate priority buckets")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
