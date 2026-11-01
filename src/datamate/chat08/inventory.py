from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


FAMILY_ORDER = [
    "industry-specific",
    "COGS/profit",
    "inventory",
    "purchase",
    "payment/debt",
    "customer ranking/loyalty",
    "product ranking",
    "product quantity",
    "revenue share",
    "max/min day",
    "average order value",
    "cancel count/rate",
    "order count",
    "growth/comparison",
    "direct revenue",
]


RULES: dict[str, list[tuple[str, str]]] = {
    "direct revenue": [
        ("REV_01", r"\bdoanh\s*thu\b|\bdoanh\s*số\b"),
        ("REV_02", r"tổng\s+(?:số\s+)?tiền\s+(?:bán|hàng)|tiền\s+bán"),
        ("REV_03", r"bán\s+được\s+(?:(?:bao\s+)?nhiêu\s+)?tiền|thu\s+về\s+(?:bao\s+)?nhiêu"),
        ("REV_04", r"(?:tổng\s+cộng|tổng)\s+(?:được\s+)?bao\s+nhiêu\s+tiền|revenue"),
        ("REV_05", r"bán.{1,100}được\s+(?:bao\s+)?nhiêu\s+tiền"),
    ],
    "order count": [
        ("ORD_01", r"(?:bao\s+nhiêu|số|tổng\s+số)\s+(?:đơn(?:\s+hàng)?|hóa\s*đơn|hoá\s*đơn)"),
        ("ORD_02", r"đếm\s+(?:số\s+)?(?:đơn|hóa\s*đơn|hoá\s*đơn)"),
        ("ORD_03", r"(?:có|được|bán)\s+(?:bao\s+nhiêu|mấy)\s+(?:đơn|hóa\s*đơn|hoá\s*đơn)|(?:bao\s+nhiêu|mấy)\s+(?:đơn|hóa\s*đơn|hoá\s*đơn)"),
    ],
    "cancel count/rate": [
        ("CAN_01", r"\b(?:hủy|huỷ)\b"),
        ("CAN_02", r"t[ỉỷy]\s*lệ\s+(?:đơn\s+)?(?:hủy|huỷ)"),
    ],
    "average order value": [
        ("AOV_01", r"(?:giá\s*trị|tiền|doanh\s*thu)\s+trung\s+bình\s+(?:mỗi|một)\s+(?:đơn|hóa\s*đơn|phiếu)"),
        ("AOV_02", r"trung\s+bình\s+(?:mỗi|một)\s+(?:đơn|hóa\s*đơn|phiếu)"),
        ("AOV_03", r"bình\s+quân\s+(?:mỗi|một|1)\s+(?:đơn|hóa\s*đơn|phiếu)|(?:mỗi|một|1)\s+(?:đơn|hóa\s*đơn|phiếu).*bình\s+quân"),
        ("AOV_04", r"trung\s+bình\s+(?:mỗi|một|1)\s+(?:đơn|hóa\s*đơn|phiếu)|(?:mỗi|một|1)\s+(?:đơn|hóa\s*đơn|phiếu).*trung\s+bình"),
        ("AOV_05", r"trung\s+bình.*(?:mỗi|một|1)\s+(?:đơn|hóa\s*đơn|phiếu)"),
    ],
    "growth/comparison": [
        ("CMP_01", r"so\s+với|so\s+sánh|kỳ\s+trước|tháng\s+trước|quý\s+trước|năm\s+trước"),
        ("CMP_02", r"tăng\s*trưởng|phần\s+trăm\s+(?:thay\s+đổi|tăng|giảm)|thay\s+đổi\s+bao\s+nhiêu"),
        ("CMP_03", r"chênh\s*lệch|hơn\s+bao\s+nhiêu|kém\s+bao\s+nhiêu|tăng\s+bao\s+nhiêu|giảm\s+bao\s+nhiêu"),
        ("CMP_04", r"tháng\s+nào.*(?:cao|nhiều|lớn|thấp|ít|nhỏ).*nhất"),
    ],
    "max/min day": [
        ("DAY_01", r"ngày\s+(?:nào|mấy).*(?:cao|nhiều|lớn|thấp|ít|nhỏ).*nhất"),
        ("DAY_02", r"(?:cao|nhiều|lớn|thấp|ít|nhỏ)\s+nhất.*ngày\s+(?:nào|mấy)"),
    ],
    "revenue share": [
        ("SHR_01", r"t[ỉỷy]\s*(?:trọng|lệ).*doanh\s*thu|chiếm\s+bao\s+nhiêu\s*%.*doanh\s*thu"),
        ("SHR_02", r"phần\s+trăm\s+doanh\s*thu"),
    ],
    "product quantity": [
        ("QTY_01", r"(?:số\s*lượng|sản\s*lượng).*bán"),
        ("QTY_02", r"tổng\s+(?:số\s+)?(?:chai|ly|lon|hộp|gói|bịch|cái|chiếc|kg|kilogram|viên|thùng|mét|m2|m²)"),
        ("QTY_03", r"bán\s+(?:ra|được)\s+(?:tổng\s+cộng\s+)?(?:bao\s+nhiêu|mấy)\s+(?:chai|ly|lon|hộp|gói|bịch|cái|chiếc|kg|kilogram|viên|thùng|mét|m2|m²|cây|đĩa|dĩa|tô|suất|phần|bình|cục|vỉ)"),
        ("QTY_04", r"số\s+(?:chai|ly|lon|hộp|gói|bịch|cái|chiếc|kg|viên|thùng|mét|m2|m²|cây|đĩa|dĩa|tô|suất|phần|bình|cục|vỉ).*bán"),
    ],
    "product ranking": [
        ("PRD_01", r"(?:mặt\s+hàng|sản\s+phẩm|món|thuốc).*(?:bán\s+chạy|bán\s+(?:được\s+)?nhiều|hot|doanh\s*thu|lời).*(?:nhất|top)"),
        ("PRD_02", r"(?:top\s*\d+|xếp\s+hạng).*(?:mặt\s+hàng|sản\s+phẩm|món|hàng|thuốc)"),
        ("PRD_03", r"(?:mặt\s+hàng|sản\s+phẩm|món|thuốc)\s+nào.*(?:nhất|cao\s+nhất|thấp\s+nhất)"),
        ("PRD_04", r"(?:hàng|món|sản\s+phẩm)\s+nào\s+(?:chạy|hot)\s+nhất"),
    ],
    "customer ranking/loyalty": [
        ("CUS_01", r"khách(?:\s+hàng)?.*(?:mua|chi|doanh\s*thu|nợ).*(?:nhiều|cao|lớn).*(?:nhất|top)"),
        ("CUS_02", r"(?:top\s*\d+|xếp\s+hạng).*khách"),
        ("CUS_03", r"khách\s+(?:quen|trung\s+thành|quay\s+lại|thành\s+viên|mới)|mua\s+lại|nhiều\s+lần"),
        ("CUS_04", r"khách.*(?:từ|ít\s+nhất)\s+\d+\s+đơn|bao\s+nhiêu\s+khách"),
    ],
    "payment/debt": [
        ("DEBT_01", r"công\s*nợ|\bnợ\b|còn\s+nợ|mua\s+chịu|tuổi\s+nợ|quá\s+hạn"),
        ("DEBT_02", r"thu\s+nợ|trả\s+nợ|thanh\s+toán|tiền\s+mặt|chuyển\s+khoản|\bcod\b"),
        ("DEBT_03", r"chưa\s+trả|đã\s+trả|phải\s+thu|còn\s+phải\s+thu"),
        ("DEBT_04", r"bán\s+chịu|mua\s+chịu|ngày\s+phải\s+trả"),
    ],
    "purchase": [
        ("PUR_01", r"nhập\s+hàng|phiếu\s+nhập|đơn\s+nhập|tiền\s+nhập|giá\s+nhập"),
        ("PUR_02", r"nhà\s+cung\s+cấp"),
        ("PUR_03", r"đánh\s+hàng\s+về|nhập\s+vào|mua\s+vào"),
    ],
    "inventory": [
        ("INV_01", r"\btồn\s*kho\b|\bhàng\s+tồn\b|giá\s+trị\s+tồn"),
        ("INV_02", r"hết\s+hàng|còn\s+(?:bao\s+nhiêu\s+)?(?:hàng|sản\s+phẩm)|không\s+bán\s+được"),
    ],
    "COGS/profit": [
        ("PRO_01", r"giá\s*vốn|vốn\s+hàng\s+bán"),
        ("PRO_02", r"lãi\s*gộp|lãi\s*ròng|lợi\s*nhuận|\blời\b|tiền\s+lãi"),
        ("PRO_03", r"chi\s*phí"),
    ],
    "industry-specific": [
        ("IND_RX", r"kê\s+đơn|hoạt\s+chất|hạn\s+sử\s+dụng|hết\s+hạn|lô\s+(?:thuốc|hàng)"),
        ("IND_REPAIR", r"sửa\s+xe|lượt\s+xe|biển\s+số|bảo\s+hành|nhớt|vá\s+xe|ắc\s*quy"),
        ("IND_PHONE", r"thu\s+máy\s+cũ|trả\s+góp|dòng\s+máy|điện\s+thoại|iphone|máy\s+bán"),
        ("IND_BABY", r"bỉm\s+tã|sữa\s+bột|mẹ\s+và\s+bé|độ\s+tuổi|tháng\s+tuổi"),
        ("IND_CAFE", r"size\s*[ml]|ca\s+sáng|ca\s+chiều|phí\s+phục\s+vụ"),
        ("IND_DELIVERY", r"đợt\s+giao|giao\s+hàng|ngày\s+giao"),
    ],
}


CAPABILITY_BY_FAMILY = {
    "direct revenue": ["sales", "orders/status", "time"],
    "order count": ["orders/status", "time"],
    "cancel count/rate": ["orders/status", "time"],
    "average order value": ["sales", "orders/status", "time"],
    "growth/comparison": ["time", "metric-dependent"],
    "max/min day": ["sales", "orders/status", "time", "group-by-day"],
    "revenue share": ["sales", "orders/status", "grouping", "time"],
    "product quantity": ["sales", "products/units", "orders/status", "time"],
    "product ranking": ["sales", "products/units", "orders/status", "ranking", "time"],
    "customer ranking/loyalty": ["sales", "customers", "orders/status", "ranking", "time"],
    "payment/debt": ["orders/status", "payments/debt", "customers", "time"],
    "purchase": ["inventory/purchases", "products/units", "time"],
    "inventory": ["inventory/purchases", "products/units", "snapshot-time"],
    "COGS/profit": ["sales", "orders/status", "COGS/expenses", "time"],
    "industry-specific": ["industry-adapter", "metric-dependent", "time"],
    "unsupported/unknown": ["unknown"],
}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text).replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text)).lower()
    replacements = {
        r"\bd\s*thu\b|\bdthu\b": "doanh thu",
        r"\bbnhiu\b|\bbn\b": "bao nhieu",
        r"\bdc\b|\bđc\b": "duoc",
        r"\bdh\b|\bđh\b": "don hang",
        r"\bsp\b": "san pham",
        r"\bncc\b": "nha cung cap",
        r"\bhnay\b": "hom nay",
        r"\btieenf\b|\btieen\b": "tien",
        r"\bbans\b": "ban",
        r"\bnhiu\b|\bnhìu\b": "nhieu",
        r"\bth\s*(\d{1,2})\b": r"thang \1",
        r"\bt(\d{1,2})\b": r"thang \1",
    }
    for pattern, value in replacements.items():
        text = re.sub(pattern, value, text)
    return re.sub(r"\s+", " ", text).strip()


def _matches(text: str, family: str) -> list[str]:
    folded = _fold(text)
    return [
        rule_id
        for rule_id, pattern in RULES[family]
        if re.search(pattern, text, flags=re.I) or re.search(_fold(pattern), folded, flags=re.I)
    ]


def detect_period(text: str) -> tuple[str, list[str]]:
    checks = [
        ("today", r"\bhôm\s+nay\b"),
        ("yesterday", r"\bhôm\s+qua\b"),
        ("explicit_day", r"(?:ngày\s+)?\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"),
        ("recent_n_days", r"\d+\s+ngày\s+(?:gần|vừa|qua)"),
        ("week", r"\btuần\b"),
        ("month", r"\btháng\s+(?:này|trước|rồi|\d{1,2})\b"),
        ("quarter", r"\bquý\s+(?:này|trước|[1-4])\b"),
        ("year_to_date", r"từ\s+đầu\s+năm"),
        ("year", r"\bnăm\s+20\d{2}\b"),
        ("range", r"\btừ\b.+\bđến\b"),
        ("tet", r"\btết\b"),
        ("snapshot", r"đến\s+hết|tính\s+đến|cuối\s+ngày|còn\s+(?:nợ|tồn|hàng)"),
    ]
    hits = [name for name, pattern in checks if re.search(pattern, text)]
    if not hits:
        return "unspecified", []
    priority = ["snapshot", "range", "recent_n_days", "explicit_day", "today", "yesterday", "week", "month", "quarter", "year_to_date", "year", "tet"]
    return next(p for p in priority if p in hits), hits


def detect_comparison(text: str) -> str:
    if re.search(r"tăng\s*trưởng|phần\s+trăm\s+(?:thay\s+đổi|tăng|giảm)", text):
        return "growth_percent"
    if re.search(r"chênh\s*lệch|hơn\s+bao\s+nhiêu|kém\s+bao\s+nhiêu|tăng\s+bao\s+nhiêu|giảm\s+bao\s+nhiêu", text):
        return "absolute_difference"
    if re.search(r"so\s+với|so\s+sánh|kỳ\s+trước|tháng\s+trước|quý\s+trước|năm\s+trước", text):
        return "comparison_unspecified"
    return "none"


def detect_grouping(text: str) -> list[str]:
    patterns = {
        "day": r"theo\s+ngày|ngày\s+nào",
        "product": r"mặt\s+hàng|sản\s+phẩm|món|thuốc",
        "product_group": r"nhóm\s+hàng|loại\s+hàng|danh\s+mục",
        "customer": r"khách(?:\s+hàng)?",
        "customer_group": r"nhóm\s+khách",
        "payment_method": r"hình\s+thức\s+thanh\s+toán|tiền\s+mặt|chuyển\s+khoản|\bcod\b",
        "employee": r"nhân\s+viên|thợ",
        "supplier": r"nhà\s+cung\s+cấp",
        "brand": r"\bhãng\b|thương\s+hiệu",
        "shift": r"ca\s+sáng|ca\s+chiều",
    }
    return [name for name, pattern in patterns.items() if re.search(pattern, text)]


def detect_top_k(text: str) -> str:
    m = re.search(r"\btop\s*(\d+)\b", text)
    if m:
        return m.group(1)
    if re.search(r"(?:cao|nhiều|lớn|thấp|ít|nhỏ|bán\s+chạy|hot)\s+nhất", text):
        return "1"
    return ""


def detect_entity_filter(text: str) -> list[str]:
    cues = []
    for label, pattern in [
        ("named_group", r"nhóm\s+[^,?.]+"),
        ("named_product", r"(?:mặt\s+hàng|sản\s+phẩm|món)\s+[^,?.]+"),
        ("named_customer", r"khách(?:\s+hàng)?\s+[^,?.]+"),
        ("named_brand", r"hãng\s+[^,?.]+"),
        ("status", r"đơn\s+(?:hủy|huỷ|trả|đang\s+giao)"),
    ]:
        if re.search(pattern, text):
            cues.append(label)
    return cues


def classify(question: str) -> dict[str, str]:
    text = normalize(question)
    matched: dict[str, list[str]] = {f: _matches(text, f) for f in FAMILY_ORDER}
    families = [f for f in FAMILY_ORDER if matched[f]]

    # Structural operators take precedence over the underlying metric, then
    # domain-specific metrics. This creates one stable primary while retaining
    # all matched families as secondary labels.
    if "max/min day" in families:
        primary = "max/min day"
    elif "revenue share" in families:
        primary = "revenue share"
    elif "average order value" in families:
        primary = "average order value"
    elif "growth/comparison" in families:
        primary = "growth/comparison"
    else:
        primary = next((f for f in FAMILY_ORDER if f in families), "unsupported/unknown")

    secondary = [f for f in families if f != primary]
    period_type, period_hits = detect_period(text)
    rule_ids = [rid for f in families for rid in matched[f]]

    strong_primary = primary != "unsupported/unknown" and bool(matched.get(primary))
    ambiguity_reasons = []
    if primary == "unsupported/unknown":
        ambiguity_reasons.append("no_family_rule_match")
    if len(families) >= 4:
        ambiguity_reasons.append("many_overlapping_families")
    if period_type == "unspecified":
        ambiguity_reasons.append("period_unspecified")
    if primary == "industry-specific" and len(families) == 1:
        ambiguity_reasons.append("industry_metric_needs_adapter")
    if re.search(r"nhà\s+cung\s+cấp.*(?:uy\s+tín|chính)|(?:uy\s+tín|chính).*nhà\s+cung\s+cấp", text):
        ambiguity_reasons.append("subjective_supplier_term")

    confidence = "high" if strong_primary and len(ambiguity_reasons) == 0 else "medium" if strong_primary else "low"
    metric = primary
    if primary == "growth/comparison" and secondary:
        metric = secondary[0]
    elif primary in {"max/min day", "revenue share"} and "direct revenue" in secondary:
        metric = "revenue"

    capabilities = []
    for fam in [primary] + secondary:
        for cap in CAPABILITY_BY_FAMILY.get(fam, []):
            if cap not in capabilities:
                capabilities.append(cap)

    return {
        "primary_family": primary,
        "secondary_families": "|".join(secondary),
        "family": "|".join([primary] + secondary),
        "metric": metric,
        "period_type": period_type,
        "comparison_type": detect_comparison(text),
        "grouping": "|".join(detect_grouping(text)),
        "entity_filter": "|".join(detect_entity_filter(text)),
        "top_k": detect_top_k(text),
        "required_capabilities": "|".join(capabilities or ["unknown"]),
        "classifier_source": "rule_ids:" + "|".join(rule_ids) if rule_ids else "rule_ids:none",
        "classifier_confidence": confidence,
        "ambiguity": "|".join(ambiguity_reasons),
        "period_rule_hits": "|".join(period_hits),
    }


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_inventory(split_root: Path, split: str) -> list[dict[str, str]]:
    questions = read_jsonl(split_root / "questions.jsonl")
    answers = {}
    if split == "train":
        answers = {row["id"]: row for row in read_jsonl(split_root / "answers.jsonl")}
    rows = []
    for q in questions:
        row = {
            "question_id": q["id"],
            "split": split,
            "business_id": q["business_id"],
            "question": q["question"],
            "as_of_date": q["as_of_date"],
            "answer_type": answers.get(q["id"], {}).get("type", ""),
        }
        row.update(classify(q["question"]))
        rows.append(row)
    return rows


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_summary(train: list[dict], public: list[dict]) -> list[dict]:
    rows = []
    for split, data in [("train", train), ("public_test", public)]:
        by = defaultdict(list)
        for row in data:
            by[row["primary_family"]].append(row)
        for family in sorted(by):
            group = by[family]
            rows.append({
                "split": split,
                "primary_family": family,
                "question_count": len(group),
                "business_count": len({r["business_id"] for r in group}),
                "high_confidence_count": sum(r["classifier_confidence"] == "high" for r in group),
                "medium_confidence_count": sum(r["classifier_confidence"] == "medium" for r in group),
                "low_confidence_count": sum(r["classifier_confidence"] == "low" for r in group),
                "ambiguous_count": sum(bool(r["ambiguity"]) for r in group),
                "question_ids": "|".join(r["question_id"] for r in group),
            })
    return rows


def stratified_sample(train: list[dict], public: list[dict], per_stratum: int = 3) -> list[dict]:
    sampled = []
    for split, data in [("train", train), ("public_test", public)]:
        strata = defaultdict(list)
        for row in data:
            strata[row["primary_family"]].append(row)
        for family, group in sorted(strata.items()):
            # Deterministic spread across businesses and confidence levels.
            group = sorted(group, key=lambda r: (r["classifier_confidence"], r["business_id"], r["question_id"]))
            chosen = []
            seen_biz = set()
            for row in group:
                if row["business_id"] not in seen_biz:
                    chosen.append(row)
                    seen_biz.add(row["business_id"])
                if len(chosen) >= per_stratum:
                    break
            for row in chosen:
                sampled.append({
                    "question_id": row["question_id"],
                    "split": split,
                    "business_id": row["business_id"],
                    "question": row["question"],
                    "answer_type": row["answer_type"],
                    "predicted_primary_family": family,
                    "predicted_secondary_families": row["secondary_families"],
                    "classifier_confidence": row["classifier_confidence"],
                    "ambiguity": row["ambiguity"],
                    "manual_review_status": "pending",
                    "manual_primary_family": "",
                    "manual_secondary_families": "",
                    "review_notes": "",
                })
    return sampled


def validate_inventory(train: list[dict], public: list[dict]) -> dict:
    result = {}
    for split, rows, expected in [("train", train, 3000), ("public_test", public, 1000)]:
        ids = [r["question_id"] for r in rows]
        result[split] = {
            "count": len(rows),
            "expected_count": expected,
            "unique_ids": len(set(ids)),
            "duplicate_ids": sorted(qid for qid, count in Counter(ids).items() if count > 1),
            "missing_primary_family": sum(not r["primary_family"] for r in rows),
            "unknown_count": sum(r["primary_family"] == "unsupported/unknown" for r in rows),
            "ambiguous_count": sum(bool(r["ambiguity"]) for r in rows),
            "business_count": len({r["business_id"] for r in rows}),
        }
    result["passed"] = (
        result["train"]["count"] == 3000
        and result["public_test"]["count"] == 1000
        and result["train"]["unique_ids"] == 3000
        and result["public_test"]["unique_ids"] == 1000
        and result["train"]["business_count"] == 30
        and result["public_test"]["business_count"] == 14
        and result["train"]["missing_primary_family"] == 0
        and result["public_test"]["missing_primary_family"] == 0
    )
    return result


def run(project_root: Path, output_dir: Path) -> dict:
    train = build_inventory(project_root / "train", "train")
    public = build_inventory(project_root / "public_test", "public_test")
    write_csv(output_dir / "family_inventory_train.csv", train)
    write_csv(output_dir / "family_inventory_public.csv", public)
    write_csv(output_dir / "family_summary.csv", build_summary(train, public))
    review_path = output_dir / "manual_review_sample.csv"
    prior_reviews = {}
    if review_path.exists():
        with review_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("manual_review_status") and row["manual_review_status"] != "pending":
                    prior_reviews[row["question_id"]] = row
    sample = stratified_sample(train, public)
    for row in sample:
        previous = prior_reviews.get(row["question_id"])
        if previous:
            for key in ("manual_review_status", "manual_primary_family", "manual_secondary_families", "review_notes"):
                row[key] = previous.get(key, row[key])
    write_csv(review_path, sample)
    validation = validate_inventory(train, public)
    (output_dir / "inventory_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"train": train, "public": public, "validation": validation}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build multi-label DataMate question inventory")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.project_root, args.output_dir)
    print(json.dumps(result["validation"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
