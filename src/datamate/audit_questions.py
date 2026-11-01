from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


def read_jsonl(path: Path, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows

    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                errors.append({"file": str(path), "line": line_no, "error": "empty_line"})
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({
                    "file": str(path),
                    "line": line_no,
                    "error": "invalid_json",
                    "detail": str(exc),
                })
                continue
            if not isinstance(value, dict):
                errors.append({
                    "file": str(path),
                    "line": line_no,
                    "error": "row_is_not_object",
                })
                continue
            rows.append(value)
    return rows


def first_value(row: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return None


def audit_split(root: Path, split: str, errors: list[dict[str, Any]]) -> dict[str, Any]:
    questions_path = root / "questions.jsonl"
    answers_path = root / "answers.jsonl"

    questions = read_jsonl(questions_path, errors)
    answers = read_jsonl(answers_path, errors) if answers_path.exists() else []

    question_ids: list[str] = []
    answer_ids: list[str] = []
    duplicate_question_ids: list[str] = []
    duplicate_answer_ids: list[str] = []
    missing_question_id = 0
    missing_answer_id = 0
    missing_business_folder: list[dict[str, Any]] = []
    invalid_as_of_date: list[dict[str, Any]] = []

    seen_questions: set[str] = set()
    seen_answers: set[str] = set()

    data_root = root / "data"

    for line_no, row in enumerate(questions, 1):
        raw_id = first_value(row, ("id", "question_id"))
        if raw_id is None or str(raw_id).strip() == "":
            missing_question_id += 1
        else:
            value = str(raw_id)
            question_ids.append(value)
            if value in seen_questions:
                duplicate_question_ids.append(value)
            seen_questions.add(value)

        business_id = first_value(row, ("business_id", "biz_id"))
        if business_id is not None and not (data_root / str(business_id)).is_dir():
            missing_business_folder.append({
                "line": line_no,
                "business_id": str(business_id),
            })

        as_of_date = first_value(row, ("as_of_date", "date"))
        if as_of_date not in (None, ""):
            try:
                date.fromisoformat(str(as_of_date))
            except ValueError:
                invalid_as_of_date.append({
                    "line": line_no,
                    "value": as_of_date,
                })

    for row in answers:
        raw_id = first_value(row, ("id", "question_id"))
        if raw_id is None or str(raw_id).strip() == "":
            missing_answer_id += 1
        else:
            value = str(raw_id)
            answer_ids.append(value)
            if value in seen_answers:
                duplicate_answer_ids.append(value)
            seen_answers.add(value)

    question_id_set = set(question_ids)
    answer_id_set = set(answer_ids)

    return {
        "split": split,
        "root": str(root),
        "question_count": len(questions),
        "answer_count": len(answers),
        "answers_file_present": answers_path.exists(),
        "question_id_missing_count": missing_question_id,
        "answer_id_missing_count": missing_answer_id,
        "duplicate_question_ids": sorted(set(duplicate_question_ids)),
        "duplicate_answer_ids": sorted(set(duplicate_answer_ids)),
        "answers_without_question": sorted(answer_id_set - question_id_set),
        "questions_without_answer": (
            sorted(question_id_set - answer_id_set)
            if answers_path.exists()
            else None
        ),
        "missing_business_folder": missing_business_folder,
        "invalid_as_of_date": invalid_as_of_date,
        "jsonl_errors": [
            error for error in errors
            if error["file"].startswith(str(root))
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-root", type=Path, required=True)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    errors: list[dict[str, Any]] = []
    report = {
        "train": audit_split(args.train_root, "train", errors),
        "public_test": audit_split(args.public_root, "public_test", errors),
        "note": (
            "Audit structural only; does not infer business schema or official scoring."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
