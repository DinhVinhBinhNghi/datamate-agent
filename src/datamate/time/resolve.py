"""Deterministic Vietnamese date-period resolver grounded in each split rulebook."""

from __future__ import annotations

import calendar as gregorian
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd


class PeriodResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    mode: str = "flow"

    def includes(self, value: date) -> bool:
        return self.start <= value <= self.end


def _month_end(year: int, month: int) -> date:
    return date(year, month, gregorian.monthrange(year, month)[1])


def _calendar_frame(calendar: Any) -> pd.DataFrame:
    if isinstance(calendar, pd.DataFrame):
        return calendar
    if calendar is None:
        return pd.DataFrame()
    return pd.read_csv(calendar)


def resolve_period(expression: str, as_of_date: date | str, calendar: Any, ruleset: str) -> Period:
    """Resolve supported exact expressions. Unsupported phrasing fails closed."""
    if ruleset not in {"train", "public_test"}:
        raise PeriodResolutionError(f"Unknown ruleset: {ruleset}")
    as_of = pd.Timestamp(as_of_date).date()
    text = expression.strip().lower()
    if text in {"hôm nay", "hom nay", "ngày này", "ngay nay"}:
        return Period(as_of, as_of)
    if text in {"hôm qua", "hom qua"}:
        d = as_of - timedelta(days=1)
        return Period(d, d)
    m = re.fullmatch(r"(\d+)\s+ngày gần nhất", text)
    if m:
        n = int(m.group(1))
        if n < 1:
            raise PeriodResolutionError("N ngày gần nhất requires N >= 1")
        return Period(as_of - timedelta(days=n - 1), as_of)
    if text in {"tuần này", "tuan nay"}:
        return Period(as_of - timedelta(days=as_of.weekday()), as_of)
    if text in {"tuần trước", "tuần rồi", "tuan truoc", "tuan roi"}:
        this_monday = as_of - timedelta(days=as_of.weekday())
        return Period(this_monday - timedelta(days=7), this_monday - timedelta(days=1))
    if text in {"tháng này", "thang nay"}:
        return Period(date(as_of.year, as_of.month, 1), as_of)
    if text in {"tháng trước", "thang truoc"}:
        previous_month = date(as_of.year, as_of.month, 1) - timedelta(days=1)
        end = date(previous_month.year, previous_month.month, min(as_of.day, previous_month.day))
        return Period(date(previous_month.year, previous_month.month, 1), end)
    if text in {"từ đầu năm", "từ đầu năm tới nay", "tu dau nam", "tu dau nam toi nay"}:
        return Period(date(as_of.year, 1, 1), as_of)
    m = re.fullmatch(r"tháng\s+(\d{1,2})(?:/(\d{4}))?", text)
    if m:
        month = int(m.group(1))
        if month < 1 or month > 12:
            raise PeriodResolutionError(f"Invalid month: {month}")
        year = int(m.group(2)) if m.group(2) else (as_of.year if month <= as_of.month else as_of.year - 1)
        return Period(date(year, month, 1), _month_end(year, month))
    m = re.fullmatch(r"quý\s*([1-4])(?:/(\d{4}))?", text)
    if m:
        quarter = int(m.group(1))
        year = int(m.group(2)) if m.group(2) else as_of.year
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        return Period(date(year, start_month, 1), _month_end(year, end_month))
    m = re.fullmatch(r"từ\s+(\d{1,2}/\d{1,2}/\d{4})\s+đến\s+(\d{1,2}/\d{1,2}/\d{4})", text)
    if m:
        start, end = (datetime.strptime(x, "%d/%m/%Y").date() for x in m.groups())
        if end < start:
            raise PeriodResolutionError("Period end precedes start")
        return Period(start, end)
    if text in {"tính đến hôm nay", "đến hết hôm nay"}:
        return Period(date.min, as_of, mode="snapshot_to_date")
    if text in {"tết", "dịp tết", "mùa tết"} or re.fullmatch(r"tết năm \d{4}", text):
        frame = _calendar_frame(calendar)
        if not {"date", "lunar_day", "lunar_month", "lunar_year"}.issubset(frame.columns):
            raise PeriodResolutionError("Calendar lacks lunar date fields required for Tết")
        lunar_year = int(re.search(r"\d{4}", text).group()) if re.search(r"\d{4}", text) else as_of.year
        days = frame.copy()
        days["lunar_day"] = pd.to_numeric(days["lunar_day"], errors="coerce")
        days["lunar_month"] = pd.to_numeric(days["lunar_month"], errors="coerce")
        days["lunar_year"] = pd.to_numeric(days["lunar_year"], errors="coerce")
        start_rows = days[(days.lunar_year == lunar_year - 1) & (days.lunar_month == 12) & (days.lunar_day == 23)]
        end_rows = days[(days.lunar_year == lunar_year) & (days.lunar_month == 1) & (days.lunar_day == 10)]
        if start_rows.empty or end_rows.empty:
            raise PeriodResolutionError(f"Calendar has no complete Tết window for lunar year {lunar_year}")
        return Period(pd.Timestamp(start_rows.iloc[0]["date"]).date(), pd.Timestamp(end_rows.iloc[0]["date"]).date())
    raise PeriodResolutionError(f"Unsupported period expression: {expression!r}")
