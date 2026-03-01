"""KPI calculations for the Asset Performance Analytics Dashboard."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def fleet_kpis(
    assets: pd.DataFrame,
    events: pd.DataFrame,
    readings: pd.DataFrame,
    reference_date: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Compute fleet-level KPIs.

    Args:
        assets: Assets table.
        events: Events table.
        readings: Readings table.
        reference_date: Date to use as "today" (defaults to last reading date).

    Returns:
        Dictionary of KPI name → value.
    """
    if reference_date is None:
        reference_date = readings["reading_date"].max() if not readings.empty else pd.Timestamp.now()

    total_pumps = len(assets)

    ytd_start = pd.Timestamp(reference_date.year, 1, 1)
    events_ytd = events[events["event_date"] >= ytd_start]
    failures_12mo = events[
        (events["event_type"] == "failure")
        & (events["event_date"] >= reference_date - pd.Timedelta(days=365))
    ]

    maintenance_cost_ytd = events_ytd[
        events_ytd["event_type"].isin(["maintenance", "failure"])
    ]["maintenance_cost"].sum()

    downtime_ytd = events_ytd["downtime_hours"].sum()

    return {
        "total_pumps": total_pumps,
        "failures_last_12mo": len(failures_12mo),
        "maintenance_cost_ytd": round(maintenance_cost_ytd, 2),
        "downtime_hours_ytd": round(downtime_ytd, 1),
    }


def asset_kpis(
    asset_id: str,
    assets: pd.DataFrame,
    events: pd.DataFrame,
    readings: pd.DataFrame,
    reference_date: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Compute per-asset KPIs.

    Args:
        asset_id: The pump identifier.
        assets: Assets table.
        events: Events table.
        readings: Readings table.
        reference_date: Date to use as "today".

    Returns:
        Dictionary of KPI name → value.
    """
    if reference_date is None:
        reference_date = (
            readings["reading_date"].max() if not readings.empty else pd.Timestamp.now()
        )

    asset_row = assets[assets["asset_id"] == asset_id]
    if asset_row.empty:
        return {}

    install_date = pd.to_datetime(asset_row.iloc[0]["install_date"])
    age_years = round((reference_date - install_date).days / 365.25, 2)

    asset_events = events[events["asset_id"] == asset_id].copy()
    asset_readings = readings[readings["asset_id"] == asset_id].copy()

    failures = asset_events[asset_events["event_type"] == "failure"]
    lifetime_failures = len(failures)
    failures_12mo = len(
        failures[failures["event_date"] >= reference_date - pd.Timedelta(days=365)]
    )

    # MTBF
    if len(failures) >= 2:
        failure_dates = failures["event_date"].sort_values()
        gaps = failure_dates.diff().dropna().dt.days
        mtbf = round(float(gaps.mean()), 1)
    elif len(failures) == 1:
        mtbf = (reference_date - install_date).days
    else:
        mtbf = (reference_date - install_date).days

    # MTTR
    mttr = round(float(failures["downtime_hours"].mean()), 1) if not failures.empty else 0.0

    # availability
    total_hours = (reference_date - install_date).days * 24
    total_downtime = asset_events["downtime_hours"].sum()
    availability = (
        round((total_hours - total_downtime) / total_hours * 100, 2)
        if total_hours > 0 else 100.0
    )

    ytd_start = pd.Timestamp(reference_date.year, 1, 1)
    events_ytd = asset_events[asset_events["event_date"] >= ytd_start]
    maintenance_cost_ytd = events_ytd["maintenance_cost"].sum()
    downtime_hours_ytd = events_ytd["downtime_hours"].sum()

    total_runtime = asset_readings["runtime_hours"].sum() if not asset_readings.empty else 0.0
    cost_per_runtime = (
        round(maintenance_cost_ytd / total_runtime, 4)
        if total_runtime > 0 else 0.0
    )

    # days since last maintenance
    maintenance_events = asset_events[asset_events["event_type"] == "maintenance"]
    if not maintenance_events.empty:
        last_maint = maintenance_events["event_date"].max()
        days_since_maint = (reference_date - last_maint).days
    else:
        days_since_maint = int((reference_date - install_date).days)

    # rolling averages (last 3 months)
    if not asset_readings.empty:
        recent = asset_readings.sort_values("reading_date").tail(3)
        rolling_vibration = round(float(recent["vibration_mm_s"].mean()), 3)
        rolling_temperature = round(float(recent["temperature_c"].mean()), 2)
    else:
        rolling_vibration = 0.0
        rolling_temperature = 0.0

    return {
        "age_years": age_years,
        "failures_last_12mo": failures_12mo,
        "lifetime_failures": lifetime_failures,
        "mtbf_days": mtbf,
        "mttr_hours": mttr,
        "availability_pct": availability,
        "maintenance_cost_ytd": round(maintenance_cost_ytd, 2),
        "downtime_hours_ytd": round(downtime_hours_ytd, 1),
        "cost_per_runtime_hour": cost_per_runtime,
        "days_since_last_maintenance": days_since_maint,
        "rolling_vibration_mm_s": rolling_vibration,
        "rolling_temperature_c": rolling_temperature,
    }


def failures_over_time(events: pd.DataFrame) -> pd.DataFrame:
    """Aggregate failure counts by calendar month.

    Args:
        events: Events table.

    Returns:
        DataFrame with ``period`` and ``failure_count`` columns.
    """
    failures = events[events["event_type"] == "failure"].copy()
    failures["period"] = failures["event_date"].dt.to_period("M")
    grouped = (
        failures.groupby("period").size().reset_index(name="failure_count")
    )
    grouped["period"] = grouped["period"].dt.to_timestamp()
    return grouped
