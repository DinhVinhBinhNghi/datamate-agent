from __future__ import annotations

from datetime import date
from math import isfinite

from datamate.contracts import SubmissionRecord
from datamate.validate_submission import validate_row


class FormatFailure(ValueError):
    pass


def format_answer(question_id: str, answer: dict, *, allow_unanswerable: bool = False) -> dict:
    kind, value = answer.get("type"), answer.get("value")
    if kind == "unanswerable":
        if not allow_unanswerable or value is not None:
            raise FormatFailure("unanswerable_without_proof")
        record = {"id": question_id, "type": "unanswerable", "reason": "Không có đơn trong kỳ nên mẫu số tỉ lệ huỷ bằng 0"}
    else:
        if kind in {"number", "percent"}:
            if type(value) not in (int, float) or not isfinite(value):
                raise FormatFailure("invalid_numeric_value")
            if kind == "percent" and round(value, 2) != value:
                raise FormatFailure("percent_not_rounded_to_two_decimals")
            if kind == "number" and not isinstance(value, int) and value != round(value):
                raise FormatFailure("fractional_number_requires_metric_rule")
        elif kind == "date":
            if not isinstance(value, str):
                raise FormatFailure("invalid_date_value")
            if len(value) == 7:
                date.fromisoformat(value + "-01")
            else:
                date.fromisoformat(value)
        elif kind == "boolean":
            if type(value) is not bool:
                raise FormatFailure("invalid_boolean_value")
        elif kind == "string":
            if not isinstance(value, str) or not value.strip():
                raise FormatFailure("invalid_string_value")
        elif kind == "list":
            if not isinstance(value, list):
                raise FormatFailure("invalid_list_value")
            if any(isinstance(item, (dict, list)) for item in value):
                raise FormatFailure("invalid_list_element")
        elif kind == "table":
            if not isinstance(value, dict) or set(value) != {"columns", "rows"}:
                raise FormatFailure("invalid_table_value")
        else:
            raise FormatFailure("unsupported_result_type")
        record = {"id": question_id, "type": kind, "answer": value}
    SubmissionRecord.model_validate(record)
    errors = validate_row(record, 1)
    if errors:
        raise FormatFailure("invalid_submission_shape:" + str(errors))
    return record
