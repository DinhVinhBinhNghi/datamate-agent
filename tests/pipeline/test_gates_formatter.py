import unittest
from pathlib import Path
from unittest.mock import patch

from datamate.format.answer import FormatFailure, format_answer
from datamate.run import process_question
from datamate.validation.gates import GateFailure, require_evidence


ROOT = Path.cwd()
QUESTION = {"id": "q_test", "business_id": "biz_129", "question": "Số đơn hôm qua là bao nhiêu?", "as_of_date": "2025-04-25"}
PLAN = {"plan_id": "q_test", "business_id": "biz_129", "ruleset": "train", "operation": "order_count", "period": "hôm qua", "as_of_date": "2025-04-25"}


def order_answer(value=0):
    return {"type": "number", "value": value, "evidence": {
        "business_id": "biz_129", "ruleset": "train", "rule_source": "train/rulebook.md §1",
        "period": {"start": "2025-04-24", "end": "2025-04-24", "inclusive": True},
        "source": str(ROOT / "train/data/biz_129/don_hang.csv"),
        "orders_total": 10, "orders_in_period_all_statuses": 0,
        "eligible_orders": value, "null_order_keys": 0, "duplicate_order_keys": 0,
    }}


class GateFormatterTests(unittest.TestCase):
    def test_zero_is_an_answer_and_failure_is_abstain(self):
        answer = order_answer()
        require_evidence(QUESTION, PLAN, answer, ROOT)
        self.assertEqual(format_answer("q_test", answer), {"id": "q_test", "type": "number", "answer": 0})
        with patch("datamate.run.run_question", return_value={"status": "ok", "planner_seconds": 0.0, "plan": PLAN, "execution": {"answer": answer, "runtime_seconds": 0.0}}):
            record, trace = process_question(QUESTION, ROOT, "train")
        self.assertEqual(record["answer"], 0)
        self.assertEqual(trace["decision"], "answer")
        with patch("datamate.run.run_question", side_effect=TimeoutError("slow")):
            record, trace = process_question(QUESTION, ROOT, "train")
        self.assertEqual(record["type"], "abstain")
        self.assertEqual(trace["decision"], "abstain")

    def test_missing_source_identity_period_and_join_fail(self):
        for change in (
            lambda a: a["evidence"].update(source=None),
            lambda a: a["evidence"].update(business_id="biz_128"),
            lambda a: a["evidence"]["period"].update(start="2025-04-23"),
            lambda a: a["evidence"].update(duplicate_order_keys=1),
            lambda a: a["evidence"].update(orders_in_period_all_statuses=11),
        ):
            answer = order_answer()
            change(answer)
            with self.subTest(answer=answer), self.assertRaises(GateFailure):
                require_evidence(QUESTION, PLAN, answer, ROOT)

    def test_unsupported_and_result_mismatch_fail(self):
        with self.assertRaises(GateFailure):
            require_evidence(QUESTION, {**PLAN, "operation": "free_sql"}, order_answer(), ROOT)
        with self.assertRaises(GateFailure):
            require_evidence(QUESTION, PLAN, {**order_answer(), "type": "percent"}, ROOT)
        with self.assertRaises(GateFailure):
            require_evidence(QUESTION, PLAN, {**order_answer(), "value": 1}, ROOT)

    def test_unanswerable_requires_zero_denominator_proof(self):
        plan = {**PLAN, "operation": "cancel_rate"}
        answer = order_answer()
        answer.update(type="unanswerable", value=None)
        answer["evidence"].update(cancelled_orders=0, unsupported_reason="denominator is zero")
        require_evidence(QUESTION, plan, answer, ROOT)
        self.assertEqual(format_answer("q_test", answer, allow_unanswerable=True)["type"], "unanswerable")
        answer["evidence"]["orders_in_period_all_statuses"] = 1
        with self.assertRaises(GateFailure):
            require_evidence(QUESTION, plan, answer, ROOT)
        with self.assertRaises(FormatFailure):
            format_answer("q_test", answer)

    def test_format_shapes(self):
        for kind, value in (("number", 0), ("percent", 12.45), ("date", "2025-09"), ("boolean", False), ("string", "Chị Lan"), ("list", [3, 10]), ("table", {"columns": ["name"], "rows": [["Lan"]]})):
            with self.subTest(kind=kind):
                self.assertEqual(format_answer("q_test", {"type": kind, "value": value})["type"], kind)
        for kind, value in (("number", True), ("number", 1.5), ("percent", "12%"), ("percent", 1.234), ("date", "2025-02-30"), ("boolean", 0), ("table", []), ("list", [{}])):
            with self.subTest(kind=kind, value=value), self.assertRaises((FormatFailure, ValueError)):
                format_answer("q_test", {"type": kind, "value": value})
