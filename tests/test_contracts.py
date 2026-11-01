import json
import subprocess
import sys
from pathlib import Path

from datamate.contracts import SubmissionRecord


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def test_submission_contract_accepts_abstain():
    record = SubmissionRecord.model_validate({"id": "q1", "abstain": True})
    assert record.abstain is True
    assert record.type is None


def test_submission_contract_rejects_abstain_with_type():
    try:
        SubmissionRecord.model_validate(
            {"id": "q1", "abstain": True, "type": "string"}
        )
    except Exception:
        pass
    else:
        raise AssertionError("expected validation error")


def run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "datamate.validate_submission",
            str(path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_validator_accepts_valid_fixture():
    result = run_validator(FIXTURES / "valid_submission.jsonl")
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["valid"] is True


def test_validator_rejects_invalid_fixture():
    result = run_validator(FIXTURES / "invalid_submission.jsonl")
    assert result.returncode != 0
    report = json.loads(result.stdout)
    error_names = {item["error"] for item in report["errors"]}
    assert "number_must_be_numeric_not_string" in error_names
    assert "percent_must_be_string_with_percent_sign" in error_names
    assert "date_must_be_yyyy_mm_dd" in error_names
    assert "list_must_be_json_array" in error_names
    assert report["duplicate_ids"] == ["q4"]
