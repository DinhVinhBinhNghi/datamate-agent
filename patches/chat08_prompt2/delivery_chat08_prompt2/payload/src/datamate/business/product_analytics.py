from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd

from datamate.capabilities.sales import SalesView
from datamate.planner.direct_revenue import fold_text
from datamate.time.resolve import Period


def _factors(view: SalesView, config: dict, split_root: Path) -> dict[tuple[str, str], Decimal]:
    spec = config.get("unit_conversion")
    result: dict[tuple[str, str], Decimal] = {}
    if spec:
        frame = pd.read_excel(split_root / spec["path"], sheet_name=spec.get("sheet", 0))
        for row in frame.to_dict("records"):
            result[(str(row["Tên sản phẩm"]).strip(), str(row["Đơn vị quy đổi"]).strip())] = Decimal(str(row["Tỉ lệ quy đổi"]))
    return result


def product_frame(view: SalesView, config: dict, split_root: Path, period: Period) -> pd.DataFrame:
    lines = view.lines.loc[view.lines["_eligible"] & view.lines["_order_date"].map(period.includes)].copy()
    product_col, unit_col = view.roles["product_name"], view.roles["unit"]
    if lines["_quantity"].isna().any():
        raise ValueError("unparseable quantity")
    factors = _factors(view, config, split_root)
    lines["_base_quantity"] = [
        q * factors.get((str(product).strip(), str(unit).strip()), Decimal(1))
        for q, product, unit in zip(lines["_quantity"], lines[product_col], lines[unit_col], strict=True)
    ]
    return lines


def _matched_product(question: str, products: list[str]) -> str | None:
    folded = fold_text(question)
    matches = [p for p in products if fold_text(p) in folded]
    return max(matches, key=len) if matches else None


def product_quantity(view: SalesView, config: dict, split_root: Path, period: Period, question: str) -> dict:
    lines = product_frame(view, config, split_root, period)
    product_col = view.roles["product_name"]
    product = _matched_product(question, sorted(set(lines[product_col].astype(str))))
    if product is None:
        return {"type": "unanswerable", "value": None, "evidence": {"reason": "product not uniquely evidenced"}}
    value = sum(lines.loc[lines[product_col].astype(str) == product, "_base_quantity"], Decimal(0))
    if value != value.to_integral_value():
        return {"type": "unanswerable", "value": None, "evidence": {"reason": "fractional base quantity"}}
    return {"type": "number", "value": int(value), "evidence": {"metric": "product_quantity", "product": product}}


def product_ranking(view: SalesView, config: dict, split_root: Path, period: Period, top_k: int) -> dict:
    lines = product_frame(view, config, split_root, period)
    product_col = view.roles["product_name"]
    lines = lines.loc[lines[product_col].astype(str).str.casefold() != "phí phục vụ"]
    totals = lines.groupby(product_col, sort=False)["_base_quantity"].sum().reset_index()
    totals["_name_sort"] = totals[product_col].astype(str).map(fold_text)
    totals = totals.sort_values(["_base_quantity", "_name_sort"], ascending=[False, True], kind="mergesort")
    if len(totals) < top_k:
        return {"type": "unanswerable", "value": None, "evidence": {"reason": "insufficient products"}}
    if len(totals) > top_k and totals.iloc[top_k - 1]["_base_quantity"] == totals.iloc[top_k]["_base_quantity"]:
        return {"type": "unanswerable", "value": None, "evidence": {"reason": "tie at ranking boundary"}}
    value = totals.head(top_k)[product_col].astype(str).tolist()
    return {"type": "string" if top_k == 1 else "list", "value": value[0] if top_k == 1 else value, "evidence": {"metric": "product_ranking", "top_k": top_k}}
