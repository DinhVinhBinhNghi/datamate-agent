from __future__ import annotations

import argparse
import json
import math
from datetime import date
import re
from pathlib import Path
from typing import Any

ANSWER_TYPES = {
    "number",
    "percent",
    "list",
    "date",
    "string",
    "boolean",
    "table",
    "unanswerable",
}


def load_rows(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    errors = []

    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                errors.append({"line": line_no, "error": "empty_line"})
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({
                    "line": line_no,
                    "error": "invalid_json",
                    "detail": str(exc),
                })
                continue
            if not isinstance(row, dict):
                errors.append({"line": line_no, "error": "row_is_not_object"})
                continue
            rows.append(row)

    return rows, errors


def value(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return None


def validate_row(row: dict[str, Any], line_no: int) -> list[dict[str, Any]]:
    errors = []
    def fail(reason): errors.append({"line": line_no, "error": reason})
    if not isinstance(row.get("id"), str) or not row["id"].strip(): fail("missing_or_invalid_id")
    kind, answer = row.get("type"), row.get("answer")
    if kind == "abstain":
        if answer is not None: fail("abstain_has_answer")
        return errors
    if kind not in ANSWER_TYPES:
        fail("invalid_type")
        return errors
    if kind in {"number", "percent"}:
        if isinstance(answer, bool) or not isinstance(answer, (int, float)) or not math.isfinite(answer): fail("numeric_answer_required")
    elif kind == "date":
        try:
            if not isinstance(answer, str) or not re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", answer): raise ValueError()
            date.fromisoformat(answer + "-01" if len(answer) == 7 else answer)
        except (ValueError, TypeError): fail("invalid_date")
    elif kind == "list" and not isinstance(answer, list): fail("list_required")
    elif kind == "table":
        if not isinstance(answer, dict) or set(answer) != {"columns", "rows"}: fail("table_object_required")
        else:
            cols, rows = answer["columns"], answer["rows"]
            if not isinstance(cols, list) or any(not isinstance(c, str) for c in cols) or len(cols) != len(set(cols)): fail("invalid_columns")
            if not isinstance(rows, list) or any(not isinstance(v, list) or not isinstance(cols, list) or len(v) != len(cols) for v in rows): fail("invalid_table_rows")
    elif kind == "boolean" and type(answer) is not bool: fail("boolean_required")
    elif kind == "string" and not isinstance(answer, str): fail("string_required")
    elif kind == "unanswerable" and answer is not None: fail("unanswerable_has_answer")
    try: json.dumps(row, allow_nan=False)
    except (ValueError, TypeError): fail("non_json_or_nonfinite_value")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    args = parser.parse_args()

    rows, errors = load_rows(args.submission)
    seen: set[str] = set()
    duplicate_ids: list[str] = []

    for line_no, row in enumerate(rows, 1):
        errors.extend(validate_row(row, line_no))
        record_id = value(row, "id", "question_id")
        if record_id is not None:
            record_id = str(record_id)
            if record_id in seen:
                duplicate_ids.append(record_id)
            seen.add(record_id)

    report = {
        "path": str(args.submission),
        "row_count": len(rows),
        "duplicate_ids": sorted(set(duplicate_ids)),
        "errors": errors,
        "valid": not errors and not duplicate_ids,
        "note": (
            "Local structural validator only; it is not the official scorer "
            "and applies no hidden normalization or tolerance."
        ),
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


