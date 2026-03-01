"""Overview page — fleet KPIs, failure trends, and top risky assets."""

from __future__ import annotations

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")
st.title("📊 Fleet Overview")


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
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")

min_date = events["event_date"].min().date() if not events.empty else pd.Timestamp("2019-01-01").date()
max_date = events["event_date"].max().date() if not events.empty else pd.Timestamp("2023-12-31").date()
date_range = st.sidebar.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

zones = ["All"] + sorted(assets["zone"].unique().tolist())
selected_zone = st.sidebar.selectbox("Zone", zones)

pump_types = ["All"] + sorted(assets["pump_type"].unique().tolist())
selected_type = st.sidebar.selectbox("Pump Type", pump_types)

# Apply filters to assets
filtered_assets = assets.copy()
if selected_zone != "All":
    filtered_assets = filtered_assets[filtered_assets["zone"] == selected_zone]
if selected_type != "All":
    filtered_assets = filtered_assets[filtered_assets["pump_type"] == selected_type]

filtered_ids = filtered_assets["asset_id"].tolist()
filtered_events = events[
    (events["asset_id"].isin(filtered_ids))
    & (events["event_date"] >= pd.Timestamp(date_range[0]))
    & (events["event_date"] <= pd.Timestamp(date_range[-1]))
]

reference_date = pd.Timestamp(date_range[-1])

# ---------------------------------------------------------------------------
# KPI calculations
# ---------------------------------------------------------------------------
from src.kpis import fleet_kpis, failures_over_time
from src.risk import compute_fleet_risk, add_risk_bucket

kpis = fleet_kpis(filtered_assets, filtered_events, readings, reference_date)
risk_df = compute_fleet_risk(filtered_assets, filtered_events, readings, reference_date)
risk_df = add_risk_bucket(risk_df)

high_risk_count = len(risk_df[risk_df["risk_level"].isin(["High", "Critical"])])

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Pumps", kpis["total_pumps"])
col2.metric("High Risk Assets", high_risk_count)
col3.metric("Failures (Last 12 mo)", kpis["failures_last_12mo"])
col4.metric("Maintenance Cost YTD", f"${kpis['maintenance_cost_ytd']:,.0f}")

st.divider()

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
from src.plots import failures_over_time_chart, risk_distribution_histogram

col_left, col_right = st.columns(2)

with col_left:
    failures_ts = failures_over_time(filtered_events)
    if not failures_ts.empty:
        st.plotly_chart(failures_over_time_chart(failures_ts), use_container_width=True)
    else:
        st.info("No failure events in the selected date range.")

with col_right:
    if not risk_df.empty:
        st.plotly_chart(risk_distribution_histogram(risk_df), use_container_width=True)
    else:
        st.info("No risk data available.")

st.divider()

# ---------------------------------------------------------------------------
# Top 10 risky assets table
# ---------------------------------------------------------------------------
st.subheader("🔴 Top 10 Risky Assets")

if not risk_df.empty:
    top10 = risk_df.head(10).merge(
        filtered_assets[["asset_id", "zone", "pump_type", "criticality", "replacement_cost"]],
        on="asset_id",
        how="left",
    )
    display_cols = [
        "asset_id", "zone", "pump_type", "criticality",
        "prob_failure", "risk", "risk_level",
    ]
    display_cols = [c for c in display_cols if c in top10.columns]
    st.dataframe(top10[display_cols], use_container_width=True)
else:
    st.info("No risk data to display.")
