from __future__ import annotations

from datamate.capabilities.sales import SalesView
from datamate.planner.direct_revenue import fold_text
from datamate.time.resolve import Period


def customer_spend_ranking(view: SalesView, period: Period, top_k: int) -> dict:
    lines = view.lines.loc[view.lines["_eligible"] & view.lines["_order_date"].map(period.includes)].copy()
    lines = lines.loc[lines["_customer"].notna()]
    lines = lines.loc[~lines["_customer"].map(fold_text).isin({"le", "kl", "khach le"})]
    totals = lines.groupby("_customer", sort=False)["_line_amount_vnd"].sum().reset_index()
    totals["_name_sort"] = totals["_customer"].map(fold_text)
    totals = totals.sort_values(["_line_amount_vnd", "_name_sort"], ascending=[False, True], kind="mergesort")
    if len(totals) < top_k:
        return {"type": "unanswerable", "value": None, "evidence": {"reason": "insufficient customers"}}
    if len(totals) > top_k and totals.iloc[top_k - 1]["_line_amount_vnd"] == totals.iloc[top_k]["_line_amount_vnd"]:
        return {"type": "unanswerable", "value": None, "evidence": {"reason": "tie at ranking boundary"}}
    value = totals.head(top_k)["_customer"].astype(str).tolist()
    return {"type": "string" if top_k == 1 else "list", "value": value[0] if top_k == 1 else value, "evidence": {"metric": "customer_spend_ranking", "top_k": top_k}}
