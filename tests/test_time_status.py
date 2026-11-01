from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from datamate.business.status import (
    debt_eligible,
    is_cancelled,
    is_returned,
    order_count_eligible,
    revenue_eligible,
)
from datamate.time.resolve import Period, PeriodResolutionError, resolve_period


@pytest.fixture
def calendar_frame():
    project_root = Path(__file__).resolve().parents[1]
    return pd.read_csv(project_root / "train" / "calendar.csv")


@pytest.mark.parametrize("ruleset", ["train", "public_test"])
def test_status_predicates_are_metric_specific(ruleset):
    assert revenue_eligible("completed", ruleset)
    assert revenue_eligible("shipping", ruleset)
    assert not revenue_eligible("cancelled", ruleset)
    assert not revenue_eligible("returned", ruleset)
    assert order_count_eligible("Đang vận chuyển", ruleset)
    assert not order_count_eligible("khách hủy", ruleset)
    assert is_cancelled("khách hủy", ruleset)
    assert is_returned("Đã trả hàng", ruleset)
    assert debt_eligible("returned", ruleset)
    assert not debt_eligible("completed", "cod", ruleset=ruleset)


@pytest.mark.parametrize(
    "expression,as_of,expected",
    [
        ("hôm nay", "2025-03-01", (date(2025, 3, 1), date(2025, 3, 1))),
        ("hôm qua", "2025-03-01", (date(2025, 2, 28), date(2025, 2, 28))),
        ("3 ngày gần nhất", "2024-03-01", (date(2024, 2, 28), date(2024, 3, 1))),
        ("tuần này", "2025-01-01", (date(2024, 12, 30), date(2025, 1, 1))),
        ("tuần trước", "2025-01-01", (date(2024, 12, 23), date(2024, 12, 29))),
        ("tháng này", "2024-02-29", (date(2024, 2, 1), date(2024, 2, 29))),
        ("tháng trước", "2024-03-31", (date(2024, 2, 1), date(2024, 2, 29))),
        ("từ đầu năm", "2024-02-29", (date(2024, 1, 1), date(2024, 2, 29))),
        ("tháng 2/2024", "2025-01-01", (date(2024, 2, 1), date(2024, 2, 29))),
        ("quý 4/2024", "2025-01-01", (date(2024, 10, 1), date(2024, 12, 31))),
        ("từ 28/02/2024 đến 01/03/2024", "2024-01-01", (date(2024, 2, 28), date(2024, 3, 1))),
    ],
)
def test_period_edges(expression, as_of, expected, calendar_frame):
    period = resolve_period(expression, as_of, calendar_frame, "train")
    assert (period.start, period.end) == expected
    assert period.includes(period.start) and period.includes(period.end)


def test_tet_window_from_calendar(calendar_frame):
    period = resolve_period("Tết năm 2024", "2024-01-01", calendar_frame, "train")
    assert period == Period(date(2024, 2, 2), date(2024, 2, 19))


def test_snapshot_mode_is_explicit(calendar_frame):
    period = resolve_period("đến hết hôm nay", "2024-03-01", calendar_frame, "public_test")
    assert period.mode == "snapshot_to_date"
    assert period.end == date(2024, 3, 1)


def test_unknown_ruleset_and_unsupported_period_fail_closed(calendar_frame):
    with pytest.raises(PeriodResolutionError):
        resolve_period("hôm nay", "2024-01-01", calendar_frame, "merged")
    with pytest.raises(PeriodResolutionError):
        resolve_period("kỳ tài chính", "2024-01-01", calendar_frame, "train")
