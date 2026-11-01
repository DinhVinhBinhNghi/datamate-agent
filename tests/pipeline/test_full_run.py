import json
import tempfile
import unittest
from pathlib import Path

from datamate.full_run import run


class FullRunTests(unittest.TestCase):
    def test_public_resume_and_manifest_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "public_test").mkdir()
            (root / "public_test/questions.jsonl").write_text(
                json.dumps({"id":"x","business_id":"dev_001","question":"test","as_of_date":"2026-01-01"}) + "\n", encoding="utf-8")
            first = run(root, "public_test", "unit")
            second = run(root, "public_test", "unit")
            self.assertEqual(first["decisions"], {"abstain":1})
            self.assertEqual(second["decisions"], first["decisions"])
            self.assertIsNone(first["accuracy"])
            self.assertEqual(len((root / "artifacts/runs/unit/predictions.jsonl").read_text().splitlines()), 1)
            (root / "train").mkdir()
            (root / "train/questions.jsonl").write_text((root / "public_test/questions.jsonl").read_text(), encoding="utf-8")
            with self.assertRaises(ValueError):
                run(root, "train", "unit")
