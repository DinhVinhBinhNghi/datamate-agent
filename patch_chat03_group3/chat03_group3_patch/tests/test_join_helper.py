from __future__ import annotations

import pandas as pd
import pytest

from datamate.joins import JoinValidationError, sum_header_measure_once, validated_join


def join_config(cardinality: str = "one_to_many") -> dict:
    return {
        "joins": {
            "orders_to_lines": {
                "left_source": "orders",
                "right_source": "lines",
                "left_key": "order_id",
                "right_key": "order_id",
                "expected_cardinality": cardinality,
            }
        }
    }


def test_header_total_is_summed_before_one_to_many_join() -> None:
    orders = pd.DataFrame({"order_id": ["A", "B"], "total": [100, 200]})
    lines = pd.DataFrame({"order_id": ["A", "A", "B"], "line": [1, 2, 1]})

    joined, diagnostics = validated_join(join_config(), "orders_to_lines", orders, lines)

    assert sum_header_measure_once(orders, "order_id", "total") == 300
    assert joined["total"].sum() == 400  # demonstrates why joined header totals are unsafe
    assert diagnostics["output_rows"] == 3
    assert diagnostics["row_inflation_vs_left"] == 1.5


def test_two_identical_real_detail_rows_are_preserved() -> None:
    orders = pd.DataFrame({"order_id": ["A"], "total": [100]})
    lines = pd.DataFrame({"order_id": ["A", "A"], "quantity": [1, 1]})

    joined, _ = validated_join(join_config(), "orders_to_lines", orders, lines)

    assert len(joined) == 2
    assert joined["quantity"].tolist() == [1, 1]


def test_unexpected_many_to_many_fails() -> None:
    duplicate_headers = pd.DataFrame({"order_id": ["A", "A"], "total": [100, 100]})
    lines = pd.DataFrame({"order_id": ["A", "A"], "quantity": [1, 2]})

    with pytest.raises(JoinValidationError, match="violates one_to_many"):
        validated_join(join_config(), "orders_to_lines", duplicate_headers, lines)


def test_header_sum_rejects_duplicate_keys() -> None:
    duplicate_headers = pd.DataFrame({"order_id": ["A", "A"], "total": [100, 100]})

    with pytest.raises(JoinValidationError, match="not unique/non-null"):
        sum_header_measure_once(duplicate_headers, "order_id", "total")
