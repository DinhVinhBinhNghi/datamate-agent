import json
import unittest
from pathlib import Path
from unittest.mock import patch

from datamate.run import process_question
from datamate.validate_submission import validate_row


ROOT = Path.cwd()


class RunnerTests(unittest.TestCase):
    def test_official_shapes(self):
        rows = [
            {"id": "x", "type": "percent", "answer": -12.45},
            {"id": "x", "type": "abstain"},
            {
                "id": "x",
                "type": "table",
                "answer": {"columns": ["a"], "rows": [[1]]},
            },
        ]
        for row in rows:
            self.assertEqual(validate_row(row, 1), [])
        self.assertTrue(
            validate_row({"id": "x", "type": "percent", "answer": "12%"}, 1)
        )

    def test_oracle_match(self):
        question = {
            "id": "development_oracle",
            "business_id": "biz_129",
            "question": "Tổng doanh thu tháng 1/2025 là bao nhiêu?",
            "as_of_date": "2025-01-31",
        }
        record, packet = process_question(question, ROOT, "train")
        plans = [
            json.loads(line)
            for line in (ROOT / "artifacts/business/oracle_plans_train.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        oracle = next(row for row in plans if row["operation"] == "revenue")
        self.assertEqual(record["answer"], oracle["expected_value"])
        self.assertEqual(packet["period"]["start"], "2025-01-01")

    def test_unsupported_and_failure_abstain(self):
        question = {
            "id": "x",
            "business_id": "biz_129",
            "question": "Ai nợ nhiều nhất?",
            "as_of_date": "2025-01-31",
        }
        record, _ = process_question(question, ROOT, "train")
        self.assertEqual(record, {"id": "x", "type": "abstain"})
        with patch(
            "datamate.run.run_question", side_effect=RuntimeError("mock failure")
        ):
            record, _ = process_question(question, ROOT, "train")
            self.assertEqual(record["type"], "abstain")
