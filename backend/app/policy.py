"""Business Policy Engine: each company's objectives + guardrails."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace

import pandas as pd

WEIGHT_KEYS = ["profitability", "growth", "revenue", "inventory", "cac", "risk"]


@dataclass(frozen=True)
class Policy:
    policy_id: str
    name: str
    weights: dict = field(default_factory=dict)   # profitability, growth, revenue, inventory, cac, risk (sum 1)
    min_margin: float = 0.3
    max_cac: float = 500.0
    min_roas: float = 2.0
    inventory_target_days: float = 30.0
    ltv_per_customer: float = 1000.0
    price_elasticity: float = 1.2
    risk_label: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def with_overrides(self, weights: dict | None = None, constraints: dict | None = None) -> "Policy":
        p = self
        if weights:
            w = {k: max(0.0, float(weights.get(k, self.weights[k]))) for k in WEIGHT_KEYS}
            s = sum(w.values()) or 1.0
            p = replace(p, weights={k: v / s for k, v in w.items()})
        if constraints:
            allowed = {k: float(v) for k, v in constraints.items()
                       if k in ("min_margin", "max_cac", "min_roas", "inventory_target_days") and v is not None}
            p = replace(p, **allowed)
        return p


def policy_from_row(company_name: str, row: pd.Series) -> Policy:
    return Policy(
        policy_id=str(row["company_id"]), name=company_name,
        weights={
            "profitability": float(row["w_profitability"]), "growth": float(row["w_growth"]),
            "revenue": float(row["w_revenue"]), "inventory": float(row["w_inventory"]),
            "cac": float(row["w_cac"]), "risk": float(row["w_risk"]),
        },
        min_margin=float(row["min_margin"]), max_cac=float(row["max_cac"]), min_roas=float(row["min_roas"]),
        inventory_target_days=float(row["inventory_target_days"]),
        ltv_per_customer=float(row["ltv_per_customer"]), price_elasticity=float(row["price_elasticity"]),
        risk_label=str(row["risk_label"]),
    )
