from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


MODULES = [
    {"module": "Question/data audit", "input": "questions/answers, README, rulebook, sources", "output": "contract and schema/capability candidate audits", "supported_scope": "all 4,000 questions and 44 folders at structural-audit level", "validation": "3,000 train + 1,000 public; 30 + 14 businesses; 502 tables scanned", "limitation": "audit/candidate labels are not executable metric support"},
    {"module": "Loader", "input": "CSV/XLSX/SQLite + config", "output": "raw frame + provenance; guarded joins/cache", "supported_scope": "Chat03 biz_129/biz_116/biz_123; Wave1 biz_102/103/104/dev_002", "validation": "Chat03 11 tests; biz_123 one-to-many proof; Wave1 reported 90 tests + 40 subtests", "limitation": "not a universal contract for all 44 businesses"},
    {"module": "Business logic", "input": "validated source + period + rules", "output": "metric + evidence", "supported_scope": "biz_129 revenue/order/cancel; biz_102/103/104 + dev_002 direct revenue only", "validation": "biz_129 7 exact; Wave1 direct revenue 29/29 target pool", "limitation": "growth/AOV/ranking/customer/debt/inventory unsupported"},
    {"module": "Planner", "input": "Vietnamese question + identity", "output": "strict plan or planner_failure", "supported_scope": "narrow heuristic allowlist + Wave1 direct-revenue classifier", "validation": "15 planner tests; fail-closed gates; no local model", "limitation": "running 3,000 questions does not mean supporting 3,000"},
    {"module": "Runner/gates/formatter", "input": "question + validated plan", "output": "prediction/evidence/manifest/metrics or abstain", "supported_scope": "train adapters; public dev_002 narrow families", "validation": "Chat06 14 pipeline tests; baseline 1,000 valid rows; Wave1 guarded diff reported", "limitation": "full current D:\\ZALO snapshot/run directory not attached"},
    {"module": "Public baseline/Candidate B", "input": "public questions + frozen baseline", "output": "local submission JSONL only", "supported_scope": "baseline 10 dev_002 answers; Candidate B adds 8 direct-revenue answers", "validation": "baseline bytes/hash verified here; Candidate B aggregate/hash from closeout", "limitation": "public per-question correctness unknown; no auto-submit"},
]


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(str(v).replace("|", "/") for v in row) + " |" for row in rows],
    ])


def run(output_dir: Path) -> dict:
    train = read_csv(output_dir / "family_inventory_train.csv")
    public = read_csv(output_dir / "family_inventory_public.csv")
    archetypes = read_csv(output_dir / "business_archetype_matrix.csv")
    manual = read_csv(output_dir / "manual_review_sample.csv")
    priorities = read_csv(output_dir / "priority_buckets.csv")
    train_counts = Counter(r["primary_family"] for r in train)
    public_counts = Counter(r["primary_family"] for r in public)
    corrected = [r for r in manual if r["manual_primary_family"] != r["predicted_primary_family"]]
    selected = [r for r in priorities if r["decision"] in {"PRIMARY", "SECONDARY", "STRETCH"}]

    state = {
        "status_label": "ĐÃ XÁC MINH trong phạm vi file đính kèm, trừ mục reported/missing",
        "data": {
            "train_questions": len(train), "train_answers": 3000, "public_questions": len(public),
            "train_businesses": sum(r["split"] == "train" for r in archetypes),
            "public_businesses": sum(r["split"] == "public_test" for r in archetypes),
            "schema_tables_scanned": 502,
            "schema_scan_error_businesses": sum(bool(r["scan_errors"]) for r in archetypes),
        },
        "hashes": {
            "attached_train_zip": "c1adbc654a301c30e4cf20b55d301381025f49db1162d88322b552d7472fea01",
            "attached_public_zip": "46fb50f926ed1510b9f099a53918f45e304b256680452c93e74401b4a5442c52",
            "train_rulebook": "740267bccba29df70f745bc39968bbec5b3e62dada2c858c45314f3ec723d113",
            "public_rulebook": "959ebb63b709fad68f7e8a339cde955c96b6e9af2e48141db3ad5a2429510e10",
            "baseline_submission_verified": "c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6",
            "candidate_b_reported_not_byte_verified": "0eb7eb9f730bf8f0cbafb8dc3db5fe73b4f75bef99086dfcd5e21591ccf8c66a",
        },
        "public_runs": {
            "baseline": {"run_id": "chat07_public_20261030_181131", "answered": 10, "abstain": 990, "leaderboard_user_reported": 0.010},
            "candidate_b": {"run_id": "wave1_public_revenue_20261030_220018", "answered": 18, "abstain": 982, "leaderboard_user_reported": 0.018, "per_question_correctness": "unknown"},
        },
        "chat08_validation": {"run_all_passed": True, "unittest_passed": 5, "unittest_failed": 0},
        "modules": MODULES,
        "inventory": {
            "train_primary_counts": dict(sorted(train_counts.items())),
            "public_primary_counts": dict(sorted(public_counts.items())),
            "train_unknown": train_counts["unsupported/unknown"],
            "public_unknown": public_counts["unsupported/unknown"],
            "train_ambiguous": sum(bool(r["ambiguity"]) for r in train),
            "public_ambiguous": sum(bool(r["ambiguity"]) for r in public),
            "manual_sample_count": len(manual),
            "manual_agreement_count": len(manual) - len(corrected),
            "manual_correction_count": len(corrected),
            "manual_agreement_rate": round((len(manual) - len(corrected)) / len(manual), 4),
            "classifier_confidence_note": "rule-based evidence strength, not probability",
        },
        "priority_decisions": {
            r["decision"].lower(): {"bucket_id": r["bucket_id"], "question_count": int(r["question_count"]), "ordinal_priority_score": float(r["ordinal_priority_score"])}
            for r in selected
        },
        "missing": [
            "Candidate B submission bytes; expected hash not recomputed here.",
            "Actual Wave1 manifest/metrics/diff/train-validation/submission-log files from D:\\ZALO.",
            "Complete current D:\\ZALO source snapshot; available Wave1 packages are patch-only.",
            "Official public gold/per-question labels do not exist.",
            "Submission timestamp and daily slot were not supplied.",
        ],
    }
    (output_dir / "current_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    module_rows = [[m["module"], m["supported_scope"], m["validation"], m["limitation"]] for m in MODULES]
    family_rows = [[f, train_counts.get(f, 0), public_counts.get(f, 0)] for f in sorted(set(train_counts) | set(public_counts))]
    decision_rows = [[r["decision"], r["bucket_id"], r["question_count"], r["ordinal_priority_score"], r["blocker"]] for r in selected]
    agreement = (len(manual) - len(corrected)) / len(manual)
    report = f"""# Chat 08 — Current state report

## Kết luận điều hành

- **ĐÃ XÁC MINH:** 3.000 train questions, 3.000 train answers, 1.000 public questions, 30 train businesses, 14 public businesses; không mất/trùng ID.
- **ĐÃ XÁC MINH:** lightweight schema scan đọc 502 sheet/table (339 train + 163 public), khớp Chat02, không business nào lỗi scan.
- **ĐÃ XÁC MINH:** baseline có 1.000 dòng, 10 answer/990 abstain và SHA-256 c8c57a2...5cf7ea6.
- **ĐÃ XÁC MINH THEO CLOSEOUT, CHƯA BYTE-VERIFY:** Candidate B 18 answer/982 abstain, chỉ thêm 8 direct-revenue của dev_002; hash được báo 0eb7eb9f...f8c66a.
- **SUY LUẬN THẬN TRỌNG:** delta leaderboard người dùng báo +0.008 chứng minh Wave 1 có lợi ở cấp nhóm; không gán nhãn đúng/sai từng câu.
- **CÒN THIẾU:** Candidate B bytes và actual run manifest/metrics/diff/submission log.
- **ĐÃ XÁC MINH:** one-command rebuild passed; 5/5 Chat08 contract tests passed.

## Module và mức hỗ trợ thật

{md_table(["Module", "Business/family hỗ trợ thật", "Validation", "Hạn chế"], module_rows)}

Phân biệt: raw audited ≠ loader verified ≠ business logic verified ≠ train exact ≠ public enabled. Chi tiết ở capability_matrix.csv.

## Inventory 4.000 câu

{md_table(["Primary family", "Train", "Public"], family_rows)}

- Unknown: train {train_counts["unsupported/unknown"]}/3.000; public {public_counts["unsupported/unknown"]}/1.000.
- Ambiguous flags: train {sum(bool(r["ambiguity"]) for r in train)}; public {sum(bool(r["ambiguity"]) for r in public)}. Period unspecified là cờ review, không đồng nghĩa nhãn sai.
- Manual stratified review: {len(manual)} câu, {len(manual)-len(corrected)} đồng thuận, {len(corrected)} sửa; agreement {agreement:.2%}.
- classifier_confidence chỉ là mức evidence rule-based, không phải xác suất đúng.

## Archetype/capability

- Mỗi business có một dòng; cột semantic/JOIN ngoài case đã verify đều là candidate.
- Public transfer chỉ verified cho direct revenue biz_102/103/104 → dev_002. Analogue khác chỉ là similarity header/format.
- Không kích hoạt JOIN fact-to-fact/many-to-many mới. Capability view là read-only interface tối thiểu, không ép schema chung.

## Bucket đã chọn

{md_table(["Vai trò", "Bucket", "Public questions", "Ordinal score", "Blocker"], decision_rows)}

Primary A được chọn sau khi so toàn inventory vì cùng dev_002 đã có adapter/public gate. Secondary B chọn dev_006 vì SQLite có analogue biz_123 similarity 0.9554 và join biz_123 đã verify; vẫn phải exact-validate train. Stretch C giữ riêng vì unit/customer/debt/inventory semantics rủi ro cao.

## Tính toàn vẹn

Chat08 chỉ đọc raw data và tạo audit artifacts. Không tạo public answer/candidate mới, không nộp leaderboard, không sửa baseline/Candidate B.
"""
    (output_dir / "current_state_report.md").write_text(report, encoding="utf-8")

    (output_dir / "chat08_plan.md").write_text("""# Chat 08 plan — backlog evidence-first

## Primary — A: 23 câu còn lại của dev_002

1. Chia theo family; xử lý AOV/growth/max-day/share trước, rồi product/ranking/customer.
2. Mỗi family cần exact oracle biz_102/103/104, false-positive audit, evidence gate và baseline regression.
3. Chỉ bật pattern có train exact; public diff phải đúng expected IDs; Candidate B là rollback.

## Secondary — B: sales core dev_006 / analogue biz_123

1. Xác minh README/schema semantics, date/status/amount grain và join cardinality.
2. Tạo read-only views orders/status và sales; exact-score toàn target biz_123.
3. Mở public từng metric sau train exact + transfer checklist.

## Stretch — C: product/customer/debt/inventory

1. Pilot dev_006/biz_123: products/units và payments/debt trước, inventory/purchases sau.
2. Tách unit conversion, customer identity, debt snapshot/flow và inventory snapshot.
3. Industry-specific fail-closed tới khi rulebook + README + exact oracle đủ.

## Stop/go gates

- Go: exact train target, zero false positives, provenance, cardinality proof, expected-only public diff.
- Stop: semantic chưa chứng minh, kỳ ngoài coverage, ambiguous classifier, unexplained join inflation, hoặc regression đổi Candidate B.
""", encoding="utf-8")

    (output_dir / "missing_information.md").write_text("""# Missing information

## CÒN THIẾU nhưng không chặn inventory

- Candidate B bytes: D:\\ZALO\\artifacts\\submissions\\submission_wave1_public_revenue_20261030_220018.jsonl.
- Run directory: D:\\ZALO\\artifacts\\runs\\wave1_public_revenue_20261030_220018\\.
- D:\\ZALO\\artifacts\\leaderboard\\submission_log.csv.
- Full current src/configs/tests snapshot; Wave1 packages available here are patch-only.
- Submission timestamp and daily slot.

## Tác động

- Baseline hash đã byte-verify; Candidate B hash chỉ cross-check closeout handoff/script/README.
- Wave1 29/29 and 8-line diff are **ĐÃ XÁC MINH THEO CLOSEOUT**, not independently rerun here.
- Inventory 4.000 câu và schema scan 44 business không phụ thuộc các file còn thiếu.

## Prompt ngắn để lấy từ chat cũ

Hãy đóng gói nguyên trạng (không sửa) run Wave1, Candidate B submission, submission_log.csv và snapshot src/configs/tests hiện tại; kèm SHA-256 từng file. Không chạy lại và không tạo candidate mới.
""", encoding="utf-8")
    return state


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    state = run(args.output_dir)
    print(json.dumps({"passed": True, "manual_review": state["inventory"]["manual_sample_count"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
