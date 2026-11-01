from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import pandas as pd

from datamate.business.monthly_sales_revenue import _prepare_lines
from datamate.business.status import revenue_eligible
from datamate.capabilities.contracts import CapabilityContext, CapabilitySpec


_VIEW_CACHE: dict[tuple[str, str, str], "SalesView"] = {}


def _quantity(value: object) -> Decimal | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().replace(",", ".")
    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return None
    try:
        return Decimal(match.group(1))
    except InvalidOperation:
        return None


@dataclass
class SalesView:
    lines: pd.DataFrame
    roles: dict[str, str]
    evidence: dict

    def eligible(self) -> pd.DataFrame:
        return self.lines.loc[self.lines["_eligible"]].copy()


def build_sales_view(context: CapabilityContext) -> SalesView:
    config = context.config
    cache_key = (str(context.project_root.resolve()), context.split, context.business_id)
    if cache_key in _VIEW_CACHE:
        return _VIEW_CACHE[cache_key]
    lines, evidence = _prepare_lines(config, context.project_root / context.split)
    roles = config["sources"][config["monthly_sales"]["source"]]["semantic_columns"]
    status_col = roles["status"]
    lines["_eligible"] = lines[status_col].map(
        lambda value: revenue_eligible(value, context.split)
    )
    if "quantity" in roles:
        lines["_quantity"] = lines[roles["quantity"]].map(_quantity)
    if "customer_name" in roles:
        order_col = roles["order_id"]
        customer_col = roles["customer_name"]
        customers = lines.groupby(order_col, sort=False)[customer_col].transform(
            lambda s: next((str(v).strip() for v in s if pd.notna(v) and str(v).strip()), None)
        )
        lines["_customer"] = customers
    evidence = {
        **evidence,
        "capability": "sales",
        "semantic_roles": roles,
        "raw_mutated": False,
    }
    view = SalesView(lines, roles, evidence)
    _VIEW_CACHE[cache_key] = view
    return view


SALES_SPEC = CapabilitySpec(
    name="sales",
    archetype="monthly_excel_sales_lines",
    required_roles=frozenset({"order_id", "order_date", "status", "product_name", "line_amount"}),
    builder=build_sales_view,
)


def default_registry(project_root):
    from datamate.capabilities.registry import CapabilityRegistry
    registry = CapabilityRegistry(project_root)
    registry.register(SALES_SPEC)
    # products/customers reuse the same verified line view and are independently gated.
    registry.register(CapabilitySpec("products", SALES_SPEC.archetype,
        SALES_SPEC.required_roles | {"quantity", "unit"}, build_sales_view))
    registry.register(CapabilitySpec("customers", SALES_SPEC.archetype,
        SALES_SPEC.required_roles | {"customer_name"}, build_sales_view))
    return registry
