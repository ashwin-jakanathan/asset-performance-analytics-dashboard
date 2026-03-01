"""Risk Insights page — fleet-level risk analytics."""

from __future__ import annotations

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Risk Insights", page_icon="⚠️", layout="wide")
st.title("⚠️ Risk Insights")


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

from src.risk import compute_fleet_risk, add_risk_bucket
from src.plots import (
    risk_by_zone_chart,
    risk_by_age_bucket_chart,
    failures_by_mode_pareto,
    age_vs_risk_bubble,
)

reference_date = readings["reading_date"].max()
risk_df = compute_fleet_risk(assets, events, readings, reference_date)
risk_df = add_risk_bucket(risk_df)

# ---------------------------------------------------------------------------
# Row 1: Risk by Zone | Risk by Age Bucket
# ---------------------------------------------------------------------------
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(risk_by_zone_chart(risk_df, assets), use_container_width=True)
with c2:
    st.plotly_chart(risk_by_age_bucket_chart(risk_df, assets, reference_date), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Row 2: Failures by Mode (Pareto) | Age vs. Risk bubble
# ---------------------------------------------------------------------------
c3, c4 = st.columns(2)
with c3:
    if not events[events["event_type"] == "failure"].empty:
        st.plotly_chart(failures_by_mode_pareto(events), use_container_width=True)
    else:
        st.info("No failure events found.")
with c4:
    st.plotly_chart(age_vs_risk_bubble(risk_df, assets, reference_date), use_container_width=True)
