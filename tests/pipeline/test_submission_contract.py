import unittest

from pydantic import ValidationError

from datamate.contracts import SubmissionRecord
from datamate.validate_submission import validate_row


class SubmissionContractTests(unittest.TestCase):
    def test_official_abstain_shape(self):
        row = {"id": "q_1", "type": "abstain"}
        SubmissionRecord.model_validate(row)
        self.assertEqual(validate_row(row, 1), [])
        with self.assertRaises(ValidationError):
            SubmissionRecord.model_validate({"id": "q_1", "abstain": True})

    def test_official_percent_is_json_number(self):
        self.assertEqual(
            validate_row({"id": "q_2", "type": "percent", "answer": -12.45}, 1),
            [],
        )
        self.assertTrue(
            validate_row({"id": "q_2", "type": "percent", "answer": "-12.45%"}, 1)
        )

    def test_official_table_shape(self):
        valid = {
            "id": "q_3",
            "type": "table",
            "answer": {"columns": ["name", "amount"], "rows": [["Lan", 10]]},
        }
        self.assertEqual(validate_row(valid, 1), [])
        self.assertTrue(
            validate_row({"id": "q_3", "type": "table", "answer": [["Lan", 10]]}, 1)
        )
