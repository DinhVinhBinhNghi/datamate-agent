"""Metric-specific status predicates based on train/public rulebook wording."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


RULEBOOK_VERSION = {"train": "train/rulebook.md §1", "public_test": "public_test/rulebook.md §1"}


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip().casefold())


def _contains_any(value: Any, tokens: Iterable[str]) -> bool:
    if value is None:
        return False
    try:
        if value != value:  # NaN
            return False
    except Exception:
        pass
    text = _norm(value)
    return any(_norm(token) in text for token in tokens)


def _validate_ruleset(ruleset: str) -> None:
    if ruleset not in RULEBOOK_VERSION:
        raise ValueError(f"Unsupported ruleset {ruleset!r}; use train or public_test")


def is_cancelled(status: Any, ruleset: str) -> bool:
    _validate_ruleset(ruleset)
    return _contains_any(status, ("hủy", "huỷ", "cancel", "khách hủy"))


def is_returned(status: Any, ruleset: str) -> bool:
    _validate_ruleset(ruleset)
    return _contains_any(
        status,
        ("trả hàng", "đã trả hàng", "trả về", "hoàn trả", "hoàn hàng", "returned", "return"),
    )


def revenue_eligible(status: Any, ruleset: str) -> bool:
    """Rulebook: exclude cancelled and returned; in-delivery remains eligible."""
    return not is_cancelled(status, ruleset) and not is_returned(status, ruleset)


def order_count_eligible(status: Any, ruleset: str) -> bool:
    return not is_cancelled(status, ruleset) and not is_returned(status, ruleset)


def debt_eligible(status: Any, payment_method: Any = None, channel: Any = None, ruleset: str = "train") -> bool:
    """Rulebook §4: exclude cancelled; returned may remain debt-eligible."""
    _validate_ruleset(ruleset)
    if is_cancelled(status, ruleset):
        return False
    if _contains_any(payment_method, ("cod",)):
        return False
    if _contains_any(channel, ("sàn", "san", "ecommerce", "e-commerce", "marketplace")):
        return False
    return True


def purchase_eligible(status: Any, ruleset: str) -> bool:
    """Purchase status semantics need a source-specific rule; fail closed for now."""
    _validate_ruleset(ruleset)
    raise NotImplementedError("Purchase eligibility is outside the four approved families")


def period_mask(values, period, *, mode: str = "flow"):
    """Inclusive flow period mask; snapshot-to-date uses the same endpoints."""
    import pandas as pd

    parsed = pd.to_datetime(values, errors="coerce", dayfirst=False).dt.date
    if mode not in {"flow", "snapshot_to_date"}:
        raise ValueError(f"Unknown period mode {mode!r}")
    return parsed.map(lambda value: value is not None and period.start <= value <= period.end)
