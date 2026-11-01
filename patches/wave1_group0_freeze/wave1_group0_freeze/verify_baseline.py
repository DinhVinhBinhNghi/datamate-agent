"""Verify the immutable Chat 7 public baseline without modifying it."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from datamate.chat07_public_candidate import validate_candidate


EXPECTED_TYPES = {"abstain": 990, "number": 7, "percent": 3}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.project_root.resolve()
    candidate = args.candidate.resolve()
    actual_sha256 = hashlib.sha256(candidate.read_bytes()).hexdigest()
    validation = validate_candidate(candidate, root / "public_test/questions.jsonl")
    checks = {
        "sha256_matches": actual_sha256.lower() == args.expected_sha256.lower(),
        "submission_valid": validation["valid"] is True,
        "row_count_is_1000": validation["row_count"] == 1000,
        "type_counts_match": validation["type_counts"] == EXPECTED_TYPES,
        "no_duplicate_ids": not validation["duplicate_ids"],
        "no_missing_ids": not validation["missing_ids"],
        "no_extra_ids": not validation["extra_ids"],
    }
    report = {
        "run_id": "chat07_public_20261030_181131",
        "candidate": str(candidate),
        "expected_sha256": args.expected_sha256.lower(),
        "actual_sha256": actual_sha256,
        "leaderboard_score": 0.01,
        "leaderboard_score_source": "user_reported",
        "checks": checks,
        "validation": validation,
        "passed": all(checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
