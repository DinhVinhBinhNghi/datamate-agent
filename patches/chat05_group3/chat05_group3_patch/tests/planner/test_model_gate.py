"""Safety tests use mock raw strings; no model installation required."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from datamate.plan_question import lookup_question
from datamate.planner.model_gate import parse_and_gate, run_with_producer

QUESTION = lookup_question(ROOT / "train/questions.jsonl", "q_07f86ff2d62b")
VALID = json.loads((ROOT / "tests/planner/fixtures/valid_intent.json").read_text(encoding="utf-8"))


class ModelGateTests(unittest.TestCase):
    def check(self, raw, expected="planner_failure"):
        record = parse_and_gate(raw, QUESTION, ROOT, model="mock", runtime="mock", latency_seconds=.01)
        self.assertEqual(record["status"], expected, record)
        self.assertEqual(len(record["raw_sha256"]), 64)
        return record

    def test_valid_json_has_exact_oracle_plan(self):
        r = self.check(json.dumps(VALID, ensure_ascii=False), "planned")
        self.assertEqual(set(r["plan"]), {"plan_id", "operation", "business_id", "ruleset", "period", "as_of_date"})
        self.assertEqual(r["retry_count"], 0)

    def test_fence_removed_once_without_mutation(self):
        raw = "```json\n" + json.dumps(VALID, ensure_ascii=False) + "\n```"
        r = self.check(raw, "planned")
        self.assertEqual(r["retry_count"], 1)
        self.assertEqual(json.loads(json.dumps(r["parsed_intent"], ensure_ascii=False)), VALID)

    def test_hallucinated_column_and_arbitrary_sql_code(self):
        cases = ({**VALID, "entity_filter": {"column": "MadeUp"}},
                 {**VALID, "sql": "SELECT * FROM users"},
                 {**VALID, "python": "print(1)"},
                 {**VALID, "period_expression": "hôm qua; DROP TABLE orders"})
        for obj in cases:
            with self.subTest(obj=obj):
                self.check(json.dumps(obj, ensure_ascii=False))

    def test_unsupported_family_wrong_business_invalid_period(self):
        cases = ({**VALID, "family": "debt"},
                 {**VALID, "business_id": "biz_128"},
                 {**VALID, "period_expression": "tháng 13/2026"},
                 {**VALID, "period_expression": "tháng 12/2026"})
        for obj in cases:
            with self.subTest(obj=obj):
                self.check(json.dumps(obj, ensure_ascii=False))

    def test_no_semantic_repair_and_bad_syntax(self):
        r = self.check(json.dumps({**VALID, "business_id": "biz_128"}, ensure_ascii=False))
        self.assertEqual(r["retry_count"], 0)
        self.check("{bad json")

    def test_timeout_is_planner_failure_and_never_executes(self):
        def timeout(_question, _seconds, _tokens):
            raise TimeoutError("mock deadline")
        with patch("datamate.planner.model_gate.execute_plan") as oracle:
            r = run_with_producer(QUESTION, ROOT, timeout, execute=True)
        self.assertEqual(r["status"], "planner_failure")
        self.assertIn("TimeoutError", r["failure_reason"])
        oracle.assert_not_called()

    def test_invalid_output_never_executes(self):
        with patch("datamate.planner.model_gate.execute_plan") as oracle:
            r = run_with_producer(QUESTION, ROOT, lambda q, t, n: '{"sql":"DROP TABLE orders"}', execute=True)
        self.assertEqual(r["status"], "planner_failure")
        oracle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
