"""Maintenance Planner page — budget-based recommendations."""

from __future__ import annotations

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Maintenance Planner", page_icon="🔧", layout="wide")
st.title("🔧 Maintenance Planner")


@st.cache_data(ttl=300)
def load_data():
    from src.db import get_all_assets, get_all_events, get_all_readings
    assets = get_all_assets()
    events = get_all_events()
    readings = get_all_readings()
    return assets, events, readings


try:
    assets, events, readings = load_data()
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
st.sidebar.header("Planner Settings")

annual_budget = st.sidebar.slider(
    "Annual Budget ($)",
    min_value=10_000,
    max_value=1_000_000,
    value=200_000,
    step=10_000,
    format="$%d",
)

strategy = st.sidebar.radio(
    "Strategy",
    options=["maintenance", "replacement"],
    format_func=lambda s: s.capitalize(),
)

# ---------------------------------------------------------------------------
# Run planner
# ---------------------------------------------------------------------------
from src.planner import plan_maintenance

reference_date = readings["reading_date"].max()

with st.spinner("Computing maintenance plan …"):
    recommendations, summary = plan_maintenance(
        assets, events, readings,
        annual_budget=annual_budget,
        strategy=strategy,
        reference_date=reference_date,
    )

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------
st.subheader("📊 Plan Summary")
s1, s2, s3, s4 = st.columns(4)
s1.metric("Budget Total", f"${summary['budget_total']:,.0f}")
s2.metric("Budget Used", f"${summary['budget_used']:,.0f}")
s3.metric("Assets Addressed", summary["assets_addressed"])
s4.metric("Total Risk Reduced", f"{summary['total_risk_reduced']:,.0f}")

st.divider()

# ---------------------------------------------------------------------------
# Recommendations table
# ---------------------------------------------------------------------------
st.subheader("📋 Recommended Actions")
if not recommendations.empty:
    display_cols = [
        "asset_id", "action", "cost", "risk_before", "risk_after",
        "risk_reduction", "justification",
    ]
    display_cols = [c for c in display_cols if c in recommendations.columns]
    st.dataframe(
        recommendations[display_cols].style.format(
            {
                "cost": "${:,.0f}",
                "risk_before": "{:,.0f}",
                "risk_after": "{:,.0f}",
                "risk_reduction": "{:,.0f}",
            }
        ),
        use_container_width=True,
    )
else:
    st.info("No assets can be addressed within the current budget.")
