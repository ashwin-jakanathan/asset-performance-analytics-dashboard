"""Budget-based maintenance planning for the pump fleet."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.risk import compute_fleet_risk

# Default cost estimates when no historical data is available
DEFAULT_MAINTENANCE_COST = 2_000.0
DEFAULT_REPLACEMENT_COST_FACTOR = 1.0   # replacement_cost from assets table
# Risk reduction factors are conservative industry estimates:
# - Planned maintenance (cleaning, lubrication, part replacement) reduces near-term
#   failure probability by approximately 40% based on RCM literature.
# - Full replacement resets all degradation, reducing risk by ~90% (residual 10%
#   accounts for infant-mortality and installation risk).
MAINTENANCE_RISK_REDUCTION = 0.40       # maintenance reduces risk by 40 %
REPLACEMENT_RISK_REDUCTION = 0.90       # replacement reduces risk by 90 %


def plan_maintenance(
    assets: pd.DataFrame,
    events: pd.DataFrame,
    readings: pd.DataFrame,
    annual_budget: float,
    strategy: str = "maintenance",
    reference_date: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Generate a maintenance/replacement plan within *annual_budget*.

    Assets are ranked by risk-reduction-per-dollar and selected greedily until
    the budget is exhausted.

    Args:
        assets: Assets table.
        events: Events table.
        readings: Readings table.
        annual_budget: Total budget available (dollars).
        strategy: ``"maintenance"`` or ``"replacement"``.
        reference_date: Date to treat as "today".

    Returns:
        A tuple of (recommendations DataFrame, summary metrics dict).
    """
    risk_df = compute_fleet_risk(assets, events, readings, reference_date)

    # Estimate action cost and risk reduction per asset
    rows: list[dict] = []
    for _, row in risk_df.iterrows():
        asset_id = row["asset_id"]
        asset_row = assets[assets["asset_id"] == asset_id]
        if asset_row.empty:
            continue
        replacement_cost = float(asset_row.iloc[0]["replacement_cost"])

        if strategy == "replacement":
            action_cost = replacement_cost * DEFAULT_REPLACEMENT_COST_FACTOR
            reduction_factor = REPLACEMENT_RISK_REDUCTION
            action = "Replace"
        else:
            action_cost = DEFAULT_MAINTENANCE_COST
            reduction_factor = MAINTENANCE_RISK_REDUCTION
            action = "Maintain"

        risk_before = row["risk"]
        risk_after = round(risk_before * (1 - reduction_factor), 2)
        risk_reduction = risk_before - risk_after
        rr_per_dollar = risk_reduction / action_cost if action_cost > 0 else 0.0

        drivers = row.get("top_drivers", [])
        driver_str = ", ".join(drivers) if drivers else "low risk"
        justification = f"Top drivers: {driver_str}"

        rows.append(
            {
                "asset_id": asset_id,
                "action": action,
                "cost": round(action_cost, 2),
                "risk_before": round(risk_before, 2),
                "risk_after": round(risk_after, 2),
                "risk_reduction": round(risk_reduction, 2),
                "rr_per_dollar": round(rr_per_dollar, 6),
                "justification": justification,
            }
        )

    candidates = (
        pd.DataFrame(rows)
        .sort_values("rr_per_dollar", ascending=False)
        .reset_index(drop=True)
    )

    # greedy selection within budget
    selected: list[dict] = []
    budget_used = 0.0
    for _, cand in candidates.iterrows():
        if budget_used + cand["cost"] > annual_budget:
            continue
        selected.append(cand.to_dict())
        budget_used += cand["cost"]

    recommendations = pd.DataFrame(selected)

    summary: dict[str, Any] = {
        "budget_total": annual_budget,
        "budget_used": round(budget_used, 2),
        "budget_remaining": round(annual_budget - budget_used, 2),
        "assets_addressed": len(recommendations),
        "total_risk_reduced": round(
            recommendations["risk_reduction"].sum() if not recommendations.empty else 0.0, 2
        ),
    }

    return recommendations, summary
