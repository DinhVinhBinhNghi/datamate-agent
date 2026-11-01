from __future__ import annotations

import hashlib
import inspect
import json
import unittest
from pathlib import Path

from datamate.business.derived_sales import classify_derived
from datamate.evaluation import capability_eval


ROOT = Path(__file__).resolve().parents[2]


def submission(name: str) -> Path:
    options = [ROOT / "artifacts/submissions" / f"submission_{name}.jsonl", ROOT / f"submission_{name}.jsonl"]
    return next(path for path in options if path.exists())


class CapabilityExpansionTests(unittest.TestCase):
    def test_frozen_hashes(self):
        expected = {
            "chat07_public_20261030_181131": "c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6",
            "wave1_public_revenue_20261030_220018": "0eb7eb9f730bf8f0cbafb8dc3db5fe73b4f75bef99086dfcd5e21591ccf8c66a",
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256(submission(name).read_bytes()).hexdigest(), digest)

    def test_business_capability_roles_are_explicit(self):
        for split, business in [("train", "biz_102"), ("train", "biz_103"), ("train", "biz_104"), ("public_test", "dev_002")]:
            config = json.loads((ROOT / "configs/businesses" / split / f"{business}.json").read_text(encoding="utf-8"))
            roles = config["sources"]["orders"]["semantic_columns"]
            self.assertTrue({"order_id", "order_date", "status", "product_name", "line_amount", "quantity", "unit", "customer_name"} <= set(roles))

    def test_classifier_has_no_question_id_or_answer_value_allowlist(self):
        source = inspect.getsource(classify_derived)
        self.assertNotIn("q_", source)
        self.assertNotIn("answer", source)

    def test_public_examples_are_family_classified_not_id_classified(self):
        self.assertEqual(classify_derived("6-2025 trung binh 1 don dem ve bao nhieu doanh thu?", "2026-05-24").family, "average_order_value")
        self.assertEqual(classify_derived("Tháng 11/25 ngày mô quán bná nhiều tiền nhất?", "2026-05-24").family, "max_revenue_day")
        self.assertEqual(classify_derived("Th9/2025 3 khach nao chi nhieu tien nhat?", "2026-05-24").family, "customer_spend_ranking")

    def test_measured_gate_artifact_if_present(self):
        path = ROOT / "artifacts/runs/chat08_expansion_verified/capability_eval.json"
        if not path.exists():
            self.skipTest("run artifact not generated yet")
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(report["train_question_count"], 3000)
        for family in ("average_order_value", "max_revenue_day", "customer_spend_ranking"):
            self.assertTrue(report["families"][family]["public_enabled"])
            self.assertEqual(report["families"][family]["wrong"], 0)
            self.assertEqual(report["families"][family]["false_positive"], 0)
        for family in ("revenue_growth", "product_quantity", "product_ranking"):
            self.assertFalse(report["families"][family]["public_enabled"])


if __name__ == "__main__":
    unittest.main()
