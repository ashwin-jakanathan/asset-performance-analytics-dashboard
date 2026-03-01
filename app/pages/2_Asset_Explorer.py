"""Asset Explorer page — deep dive into a single pump."""

from __future__ import annotations

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Asset Explorer", page_icon="🔍", layout="wide")
st.title("🔍 Asset Explorer")


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

# Asset selector
asset_ids = sorted(assets["asset_id"].tolist())
selected_id = st.selectbox("Select Asset ID", asset_ids)

asset_row = assets[assets["asset_id"] == selected_id].iloc[0]
asset_events = events[events["asset_id"] == selected_id].sort_values("event_date")
asset_readings = readings[readings["asset_id"] == selected_id].sort_values("reading_date")

reference_date = readings["reading_date"].max()

# ---------------------------------------------------------------------------
# Asset metadata
# ---------------------------------------------------------------------------
st.subheader(f"Pump: {selected_id}")
meta_cols = st.columns(5)
meta_cols[0].metric("Type", asset_row["pump_type"])
meta_cols[1].metric("Manufacturer", asset_row["manufacturer"])
meta_cols[2].metric("Zone", asset_row["zone"])
meta_cols[3].metric("Criticality", asset_row["criticality"])
meta_cols[4].metric("Capacity (GPM)", asset_row["capacity_gpm"])

st.divider()

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
from src.kpis import asset_kpis

kpis = asset_kpis(selected_id, assets, events, readings, reference_date)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Age (years)", kpis.get("age_years", "-"))
k2.metric("MTBF (days)", kpis.get("mtbf_days", "-"))
k3.metric("MTTR (hours)", kpis.get("mttr_hours", "-"))
k4.metric("Availability (%)", kpis.get("availability_pct", "-"))

k5, k6, k7, k8 = st.columns(4)
k5.metric("Failures (12 mo)", kpis.get("failures_last_12mo", "-"))
k6.metric("Lifetime Failures", kpis.get("lifetime_failures", "-"))
k7.metric("Maintenance Cost YTD", f"${kpis.get('maintenance_cost_ytd', 0):,.0f}")
k8.metric("Days Since Last Maint.", kpis.get("days_since_last_maintenance", "-"))

st.divider()

# ---------------------------------------------------------------------------
# Risk score and explanation
# ---------------------------------------------------------------------------
from src.risk import compute_risk_for_asset

risk = compute_risk_for_asset(selected_id, assets, events, readings, reference_date)

st.subheader("⚠️ Risk Assessment")
rc1, rc2, rc3 = st.columns(3)
rc1.metric("Probability of Failure", f"{risk.get('prob_failure', 0):.2%}")
rc2.metric("Consequence ($)", f"${risk.get('consequence', 0):,.0f}")
rc3.metric("Risk Score", f"{risk.get('risk', 0):,.0f}")

drivers = risk.get("top_drivers", [])
if drivers:
    st.info(f"**Top risk drivers:** {', '.join(drivers)}")

st.divider()

# ---------------------------------------------------------------------------
# Event timeline
# ---------------------------------------------------------------------------
st.subheader("📅 Event Timeline")
from src.plots import asset_timeline_chart

if not asset_events.empty:
    st.plotly_chart(asset_timeline_chart(asset_events), use_container_width=True)
else:
    st.info("No events recorded for this asset.")

st.divider()

# ---------------------------------------------------------------------------
# Sensor readings charts
# ---------------------------------------------------------------------------
st.subheader("📈 Sensor Readings")
from src.plots import sensor_line_chart

if not asset_readings.empty:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            sensor_line_chart(asset_readings, "vibration_mm_s", "Vibration (mm/s)"),
            use_container_width=True,
        )
        st.plotly_chart(
            sensor_line_chart(asset_readings, "power_kw", "Power (kW)"),
            use_container_width=True,
        )
    with c2:
        st.plotly_chart(
            sensor_line_chart(asset_readings, "temperature_c", "Temperature (°C)"),
            use_container_width=True,
        )
        st.plotly_chart(
            sensor_line_chart(asset_readings, "flow_gpm", "Flow (GPM)"),
            use_container_width=True,
        )
else:
    st.info("No sensor readings available for this asset.")
