import csv
import unittest
from pathlib import Path


OUTPUT = Path("artifacts/chat08")


def _rows(name):
    with (OUTPUT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class Chat08ContractTests(unittest.TestCase):
    def test_question_inventory_contract(self):
        train = _rows("family_inventory_train.csv")
        public = _rows("family_inventory_public.csv")
        self.assertEqual(len(train), 3000)
        self.assertEqual(len(public), 1000)
        self.assertEqual(len({r["question_id"] for r in train}), 3000)
        self.assertEqual(len({r["question_id"] for r in public}), 1000)
        self.assertTrue(all(r["primary_family"] for r in train + public))

    def test_business_inventory_contract(self):
        rows = _rows("business_archetype_matrix.csv")
        self.assertEqual(len(rows), 44)
        self.assertEqual(sum(r["split"] == "train" for r in rows), 30)
        self.assertEqual(sum(r["split"] == "public_test" for r in rows), 14)

    def test_manual_review_is_stratified_and_completed(self):
        rows = _rows("manual_review_sample.csv")
        self.assertGreaterEqual(len(rows), 90)
        self.assertEqual({r["split"] for r in rows}, {"train", "public_test"})
        self.assertTrue(all(r["manual_review_status"] == "reviewed_chat08" for r in rows))
        self.assertEqual(sum(r["manual_primary_family"] != r["predicted_primary_family"] for r in rows), 2)

    def test_priority_traceability_and_decisions(self):
        rows = _rows("priority_buckets.csv")
        decisions = {r["decision"]: r for r in rows if r["decision"] != "not_selected"}
        self.assertEqual(decisions["PRIMARY"]["bucket_id"], "A_dev002_remaining_23")
        self.assertEqual(decisions["PRIMARY"]["question_count"], "23")
        self.assertTrue(decisions["PRIMARY"]["public_question_ids"])
        self.assertTrue(decisions["PRIMARY"]["train_analogue_question_ids"])
        self.assertEqual(decisions["SECONDARY"]["bucket_id"], "B_dev_006_sales_core")
        self.assertEqual(decisions["STRETCH"]["bucket_id"], "C_product_customer_debt_inventory")

    def test_no_submission_created_by_chat08(self):
        self.assertFalse(list(OUTPUT.glob("*submission*.jsonl")))
        self.assertFalse(list(OUTPUT.glob("*candidate*.jsonl")))


if __name__ == "__main__":
    unittest.main()
