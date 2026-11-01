"""Narrow text classifier for one-period, shop-wide direct revenue questions."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class DirectRevenueClassification:
    category: str
    period_expression: str | None = None


def fold_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
    return " ".join(
        "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").split()
    )


def _period(text: str) -> str | None:
    if re.search(r"\btu\s+dau\s+nam\b", text) or re.search(
        r"\btu\s+ngay\s+1\s*/\s*1\s+den\s+het\s+hom\s+nay\b", text
    ):
        return "từ đầu năm"
    if re.search(r"\b(?:hom|bua)\s+qua\b|\bhqua\b", text):
        return "hôm qua"
    if re.search(r"\b(?:hom|bua)\s+(?:nay|ni)\b", text):
        return "hôm nay"
    days = re.search(r"\b(\d+)\s+ngay\s+gan\s+nhat\b", text)
    if days:
        return f"{int(days.group(1))} ngày gần nhất"
    if re.search(r"\btuan\s+nay\b", text):
        return "tuần này"
    quarter = re.search(r"\bquy\s*([1-4])(?:\s+nam\s+|\s*/\s*)(20\d{2})\b", text)
    if quarter:
        return f"quý {int(quarter.group(1))}/{int(quarter.group(2))}"
    month = re.search(
        r"\b(?:thang|th|t)\s*(\d{1,2})(?:\s+nam\s+|\s*/\s*)(20\d{2})\b",
        text,
    )
    if month:
        return f"tháng {int(month.group(1))}/{int(month.group(2))}"
    short_month = re.search(
        r"(?<!\d)(?:thang\s*|th\s*|t\s*)?(\d{1,2})\s*/\s*(\d{2})(?!\d)",
        text,
    )
    if short_month:
        return f"tháng {int(short_month.group(1))}/{2000 + int(short_month.group(2))}"
    return None


def classify_direct_revenue(text: str) -> DirectRevenueClassification:
    """Classify without business IDs, question IDs, or answer values."""
    folded = fold_text(text)
    revenue_signal = "doanh thu" in folded or bool(
        re.search(
            r"\b(?:cua hang|quan)\s+ban duoc\s+(?:bao nhieu|nhieu|may)\s+tien\b",
            folded,
        )
    )
    if not revenue_signal:
        return DirectRevenueClassification("not_revenue")

    if re.search(
        r"%|phan tram|so voi|so vs|cung ky|tang truong|tang hay giam|"
        r"tang/giam|thay doi|hon hay kem|thang lien truoc|thang truoc do|"
        r"th truoc do|th trc|tang lien tuc",
        folded,
    ):
        return DirectRevenueClassification("growth_or_comparison")
    if re.search(
        r"trung binh|binh qua+n|mo+i+x?\s+don|tren mot don", folded
    ):
        return DirectRevenueClassification("average_order")
    if re.search(
        r"ngay nao|thang nao|cao nhat|lon nhat|ban dat nhat|dem so ngay|"
        r"so ngay trong|tu [0-9.,]+ dong tro len",
        folded,
    ):
        return DirectRevenueClassification("ranking_or_threshold")
    if re.search(r"\bmat hang\b|\bkhach\b|\bnhan vien\b|\bnhom\b", folded):
        return DirectRevenueClassification("entity_specific")
    if "doanh thu cua" in folded and not re.search(
        r"doanh thu cua (?:cua hang|quan)\b", folded
    ):
        return DirectRevenueClassification("entity_specific")
    if re.search(r"\bmoi thang\b|\b3 thang lien nhau\b", folded):
        return DirectRevenueClassification("multi_period")

    period = _period(folded)
    if period is None:
        return DirectRevenueClassification("other_revenue")
    return DirectRevenueClassification("direct_revenue", period)
