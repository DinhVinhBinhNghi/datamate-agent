from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from datamate.capabilities.sales import SalesView
from datamate.planner.direct_revenue import fold_text
from datamate.time.resolve import Period, resolve_period


@dataclass(frozen=True)
class DerivedIntent:
    family: str
    period: Period | None = None
    comparison_period: Period | None = None
    top_k: int | None = None


def _month_period(year: int, month: int) -> Period:
    return Period(date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]))


def _months(text: str) -> list[tuple[int, int]]:
    folded = fold_text(text)
    hits: list[tuple[int, int, int]] = []
    patterns = [
        r"(?:thang|th|t)\s*(\d{1,2})\s*(?:/|-)\s*(20\d{2}|\d{2})",
        r"(?:thang|th|t)\s*(\d{1,2})\s+nam\s+(20\d{2})",
        r"(?<!\d)(\d{1,2})\s*(?:/|-)\s*(20\d{2})(?!\d)",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, folded):
            year = int(m.group(2)); year = year + 2000 if year < 100 else year
            month = int(m.group(1))
            if 1 <= month <= 12:
                hits.append((m.start(), year, month))
    unique = []
    for _, year, month in sorted(hits):
        if (year, month) not in unique:
            unique.append((year, month))
    return unique


def _period(text: str, as_of: str) -> Period | None:
    months = _months(text)
    if months:
        return _month_period(*months[0])
    folded = fold_text(text)
    if "tuan truoc" in folded or "tuan roi" in folded:
        return resolve_period("tuần trước", as_of, None, "train")
    return None


def classify_derived(text: str, as_of: str) -> DerivedIntent:
    folded = fold_text(text)
    period = _period(text, as_of)
    if period is None:
        return DerivedIntent("unsupported")
    if re.search(r"trung binh|binh quan|gia tri trung binh", folded) and re.search(r"don|don hang", folded):
        return DerivedIntent("average_order_value", period)
    if "doanh thu" in folded or "dthu" in folded or re.search(r"nhieu tien|nhiu tien", folded):
        if re.search(r"ngay (?:nao|mo)|ngay nao|ban dat nhat", folded) and re.search(r"cao nhat|nhieu tien|dat nhat|nhiu tien", folded):
            return DerivedIntent("max_revenue_day", period)
        if re.search(r"so voi|so vs|cung ky|nam truoc|thang truoc|th truoc|thang lien|tang truong|thay doi|tang hay giam|len xuong|hon hay kem", folded):
            months = _months(text)
            if re.search(r"cung thang nam truoc|cung ky nam truoc", folded) or len(months) >= 2:
                target = max(months) if months else (period.start.year, period.start.month)
                before = (target[0] - 1, target[1])
                return DerivedIntent("revenue_growth", _month_period(*target), _month_period(*before))
            previous_end = period.start - timedelta(days=1)
            previous = _month_period(previous_end.year, previous_end.month)
            return DerivedIntent("revenue_growth", period, previous)
    if re.search(r"khach", folded) and re.search(r"chi tieu|mua nhieu tien|tong tien mua|chi nhieu tien", folded):
        match = re.search(r"top\s*([0-9]+)|(?:liet ke|cho toi|th)\s*([0-9]+)|([0-9]+)\s*khach", folded)
        top_k = int(next(v for v in match.groups() if v)) if match else 1
        return DerivedIntent("customer_spend_ranking", period, top_k=top_k)
    if re.search(r"top\s*[0-9]+|ban chay nhat|ban nhieu nhat|hang chay nhat|hang hot nhat|mon ban nhiu nhut", folded):
        if "nhom " in folded:
            return DerivedIntent("unsupported")
        match = re.search(r"top\s*([0-9]+)|(?:liet ke|cho toi)\s*([0-9]+)|([0-9]+)\s*(?:mat hang|mon)", folded)
        top_k = int(next(v for v in match.groups() if v)) if match else 1
        return DerivedIntent("product_ranking", period, top_k=top_k)
    if re.search(r"\b(?:kg|ly|chai|goi|phan)\b", folded) and re.search(r"ban (?:ra |duoc |dc )|\bso ", folded) and not re.search(r"%|thay doi|so voi|tien|doanh thu|dthu", folded):
        return DerivedIntent("product_quantity", period)
    return DerivedIntent("unsupported")


def _eligible_period(view: SalesView, period: Period):
    return view.lines.loc[view.lines["_eligible"] & view.lines["_order_date"].map(period.includes)].copy()


def revenue(view: SalesView, period: Period) -> int:
    return int(_eligible_period(view, period)["_line_amount_vnd"].sum())


def average_order_value(view: SalesView, period: Period) -> dict:
    lines = _eligible_period(view, period)
    count = int(lines[view.roles["order_id"]].nunique())
    if count == 0:
        return {"type": "unanswerable", "value": None, "evidence": {"reason": "zero eligible orders"}}
    total = int(lines["_line_amount_vnd"].sum())
    value = int((Decimal(total) / Decimal(count)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return {"type": "number", "value": value, "evidence": {"metric": "average_order_value", "numerator_revenue": total, "denominator_orders": count}}


def revenue_growth(view: SalesView, current: Period, previous: Period) -> dict:
    now, before = revenue(view, current), revenue(view, previous)
    if before == 0:
        return {"type": "unanswerable", "value": None, "evidence": {"reason": "zero comparison revenue"}}
    value = float((Decimal(now - before) * 100 / Decimal(before)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return {"type": "percent", "value": value, "evidence": {"metric": "revenue_growth", "current": now, "comparison": before}}


def max_revenue_day(view: SalesView, period: Period) -> dict:
    lines = _eligible_period(view, period)
    if lines.empty:
        return {"type": "unanswerable", "value": None, "evidence": {"reason": "no eligible sales"}}
    totals = lines.groupby("_order_date", sort=True)["_line_amount_vnd"].sum()
    maximum = totals.max()
    winners = sorted(day for day, value in totals.items() if value == maximum)
    if len(winners) != 1:
        return {"type": "unanswerable", "value": None, "evidence": {"reason": "tie for maximum day"}}
    return {"type": "date", "value": winners[0].isoformat(), "evidence": {"metric": "max_revenue_day", "revenue": int(maximum)}}
