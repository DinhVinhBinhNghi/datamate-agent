"""Run with python -m unittest discover -s tests/planner -v."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from datamate.plan_question import lookup_question, run_question
from datamate.planner.heuristic import plan_heuristic
from datamate.planner.validate import PlannerFailure, to_query_plan, validate_intent, validate_query_plan

QID = "q_07f86ff2d62b"


class PlannerGroup1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.question = lookup_question(ROOT / "train/questions.jsonl", QID)
        cls.intent = plan_heuristic(cls.question)

    def test_valid_plan_matches_oracle_contract(self):
        plan = to_query_plan(self.intent, self.question, ROOT)
        self.assertEqual(plan.operation, "revenue")
        self.assertEqual(plan.period, "tháng 3/2026")
        self.assertEqual(set(plan.to_dict()), {"plan_id", "operation", "business_id", "ruleset", "period", "as_of_date"})

    def test_json_fixtures(self):
        fixtures = ROOT / "tests/planner/fixtures"
        intent = json.loads((fixtures / "valid_intent.json").read_text(encoding="utf-8"))
        plan = json.loads((fixtures / "valid_plan.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_intent(intent, self.question, ROOT).metric, "revenue")
        self.assertEqual(validate_query_plan(plan, self.question, ROOT).operation, "revenue")
        for line in (fixtures / "invalid_plans.jsonl").read_text(encoding="utf-8").splitlines():
            invalid = json.loads(line)
            with self.subTest(case=invalid["case"]), self.assertRaises(PlannerFailure):
                validate_query_plan(invalid["plan"], self.question, ROOT)

    def test_invalid_fields_and_sql_rejected(self):
        plan = to_query_plan(self.intent, self.question, ROOT).to_dict()
        for changed in ({**plan, "sql": "select * from orders"}, {**plan, "operation": "arbitrary_python"},
                        {**plan, "business_id": "biz_128"}, {**plan, "period": "tháng 13/2026"}):
            with self.subTest(changed=changed), self.assertRaises(PlannerFailure):
                validate_query_plan(changed, self.question, ROOT)

    def test_invalid_intent_rejected(self):
        intent = self.intent.to_dict()
        for changed in ({**intent, "entity_filter": {"column": "Số phiếu"}},
                        {**intent, "family": "debt"}, {**intent, "ambiguities": ["two possible metrics"]},
                        {**intent, "operations": ["revenue", "order_count"]}):
            with self.subTest(changed=changed), self.assertRaises(PlannerFailure):
                validate_intent(changed, self.question, ROOT)

    def test_unsupported_template_fails_closed(self):
        q = {**self.question, "question": "Doanh thu nhóm hàng tháng 3/2026 là bao nhiêu?"}
        self.assertEqual(run_question(q, ROOT)["status"], "planner_failure")

    def test_local_unavailable_is_planner_failure(self):
        self.assertEqual(run_question(self.question, ROOT, "local")["reason"], "local_model_not_configured")

    def test_end_to_end(self):
        result = run_question(self.question, ROOT)
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["execution"]["answer"]["type"], "number")


if __name__ == "__main__":
    unittest.main()
