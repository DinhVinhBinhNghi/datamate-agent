"""Minimal, validated DataFrame joins with diagnostics."""

from __future__ import annotations

from typing import Any

import pandas as pd


class JoinValidationError(ValueError):
    """The configured join is absent, invalid, or violates its cardinality."""


VALID_CARDINALITIES = {"one_to_one", "one_to_many", "many_to_one"}


def _side_stats(frame: pd.DataFrame, key: str) -> dict[str, int]:
    if key not in frame.columns:
        raise JoinValidationError(f"Join key {key!r} does not exist")
    non_null = frame[key].dropna()
    return {
        "rows": int(len(frame)),
        "null_keys": int(frame[key].isna().sum()),
        "distinct_non_null_keys": int(non_null.nunique()),
        "duplicate_non_null_rows": int(non_null.duplicated().sum()),
    }


def validated_join(
    config: dict[str, Any],
    join_name: str,
    left: pd.DataFrame,
    right: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run one configured left join and return the frame plus audit diagnostics."""
    joins = config.get("joins")
    if not isinstance(joins, dict) or join_name not in joins:
        available = sorted(joins) if isinstance(joins, dict) else []
        raise JoinValidationError(
            f"Join {join_name!r} is not configured; available joins: {available}"
        )
    spec = joins[join_name]
    left_key = spec.get("left_key")
    right_key = spec.get("right_key")
    cardinality = spec.get("expected_cardinality")
    if cardinality not in VALID_CARDINALITIES:
        raise JoinValidationError(
            f"Join {join_name!r} has invalid expected_cardinality {cardinality!r}"
        )
    left_stats = _side_stats(left, left_key)
    right_stats = _side_stats(right, right_key)

    left_must_be_unique = cardinality in {"one_to_one", "one_to_many"}
    right_must_be_unique = cardinality in {"one_to_one", "many_to_one"}
    if left_must_be_unique and left_stats["duplicate_non_null_rows"]:
        raise JoinValidationError(
            f"Join {join_name!r} violates {cardinality}: left key {left_key!r} "
            f"has {left_stats['duplicate_non_null_rows']} duplicate rows"
        )
    if right_must_be_unique and right_stats["duplicate_non_null_rows"]:
        raise JoinValidationError(
            f"Join {join_name!r} violates {cardinality}: right key {right_key!r} "
            f"has {right_stats['duplicate_non_null_rows']} duplicate rows"
        )

    left_keys = set(left[left_key].dropna().unique())
    right_keys = set(right[right_key].dropna().unique())
    diagnostics: dict[str, Any] = {
        "join_name": join_name,
        "left_source": spec.get("left_source"),
        "right_source": spec.get("right_source"),
        "left_key": left_key,
        "right_key": right_key,
        "expected_cardinality": cardinality,
        "left_before": left_stats,
        "right_before": right_stats,
        "unmatched_left_distinct_keys": len(left_keys - right_keys),
        "unmatched_right_distinct_keys": len(right_keys - left_keys),
    }
    try:
        merged = left.merge(
            right,
            how="left",
            left_on=left_key,
            right_on=right_key,
            validate=cardinality,
            suffixes=("_left", "_right"),
        )
    except Exception as exc:
        raise JoinValidationError(f"Join {join_name!r} failed: {exc}") from exc
    diagnostics["output_rows"] = int(len(merged))
    diagnostics["row_inflation_vs_left"] = float(len(merged) / len(left)) if len(left) else 0.0
    return merged, diagnostics


def sum_header_measure_once(frame: pd.DataFrame, key: str, measure: str) -> int | float:
    """Sum a header-level measure only after proving one row per non-null key."""
    stats = _side_stats(frame, key)
    if stats["null_keys"] or stats["duplicate_non_null_rows"]:
        raise JoinValidationError(
            f"Cannot safely sum header measure {measure!r}: key {key!r} is not unique/non-null"
        )
    if measure not in frame.columns:
        raise JoinValidationError(f"Header measure {measure!r} does not exist")
    return frame[measure].sum()
