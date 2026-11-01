import json
from pathlib import Path

from datamate.chat07_public_candidate import validate_candidate


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_candidate_validator_checks_exact_ids_and_shapes(tmp_path):
    questions = tmp_path / "questions.jsonl"
    submission = tmp_path / "submission.jsonl"
    _write(questions, [
        {"id": "q1", "business_id": "dev_002", "question": "x", "as_of_date": "2026-01-01"},
        {"id": "q2", "business_id": "dev_003", "question": "y", "as_of_date": "2026-01-01"},
    ])
    _write(submission, [
        {"id": "q1", "type": "number", "answer": 3},
        {"id": "q2", "type": "abstain"},
    ])
    report = validate_candidate(submission, questions)
    assert report["valid"] is True
    assert report["type_counts"] == {"number": 1, "abstain": 1}
    assert report["utf8_valid"] is True
    assert report["utf8_bom"] is False


def test_candidate_validator_rejects_duplicate_and_wrong_id_order(tmp_path):
    questions = tmp_path / "questions.jsonl"
    submission = tmp_path / "submission.jsonl"
    _write(questions, [{"id": "q1"}, {"id": "q2"}])
    _write(submission, [
        {"id": "q1", "type": "abstain"},
        {"id": "q1", "type": "number", "answer": 1},
    ])
    report = validate_candidate(submission, questions)
    assert report["valid"] is False
    assert report["duplicate_ids"] == ["q1"]
    assert report["missing_ids"] == ["q2"]
