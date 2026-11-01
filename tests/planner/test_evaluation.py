"""Planner evaluation must use labels and never invoke the oracle executor."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from datamate.evaluate_planner import evaluate


class EvaluationTests(unittest.TestCase):
    def test_labelled_plan_only_evaluation(self):
        with tempfile.TemporaryDirectory() as directory, patch("datamate.plan_question.execute_plan") as oracle:
            folder = Path(directory)
            summary = evaluate(ROOT, ROOT / "tests/planner/fixtures/oracle_intents_dev.jsonl",
                               folder / "results.jsonl", folder / "report.md")
            oracle.assert_not_called()
            self.assertEqual(summary["supported_family_correct"], "5/5")
            self.assertEqual(summary["unsupported_detected"], "5/5")
            self.assertEqual(len((folder / "results.jsonl").read_text(encoding="utf-8").splitlines()), 10)


if __name__ == "__main__":
    unittest.main()
