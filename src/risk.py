"""Rule-based risk model for the Asset Performance Analytics Dashboard."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# Condition thresholds (based on typical pump industry guidelines)
# Vibration: ISO 10816-3 defines >6.3 mm/s as "unsatisfactory" for machinery
# Temperature: bearing temperature above ~80 degrees C indicates thermal degradation
# Overdue: per AWWA M49, preventive maintenance intervals should not exceed 6 months
VIBRATION_THRESHOLD = 6.0   # mm/s — above this is "bad" (ISO 10816-3 guideline)
TEMP_THRESHOLD = 80.0       # °C   — above this is "bad" (thermal degradation limit)
OVERDUE_DAYS = 180          # days without maintenance → considered overdue

# Normalisation upper bounds
MAX_ASSET_LIFE_YEARS = 20.0  # expected pump lifespan (years) for age normalisation
MAX_RECENT_FAILURES = 5.0    # number of failures in 12 months representing "saturated" risk


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp *value* to [lo, hi]."""
    return max(lo, min(hi, value))


def compute_risk_for_asset(
    asset_id: str,
    assets: pd.DataFrame,
    events: pd.DataFrame,
    readings: pd.DataFrame,
    reference_date: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Compute risk score and components for a single asset.

    The probability-of-failure score is:
        pf_score = 0.35*age_norm + 0.30*recent_fail_norm
                 + 0.20*overdue_norm + 0.15*condition_norm

    Args:
        asset_id: The pump identifier.
        assets: Assets DataFrame.
        events: Events DataFrame.
        readings: Readings DataFrame.
        reference_date: Date to treat as "today".

    Returns:
        Dictionary with keys: asset_id, age_norm, recent_fail_norm,
        overdue_norm, condition_norm, pf_score, prob_failure, consequence,
        risk, top_drivers.
    """
    if reference_date is None:
        reference_date = (
            readings["reading_date"].max() if not readings.empty else pd.Timestamp.now()
        )

    asset_row = assets[assets["asset_id"] == asset_id]
    if asset_row.empty:
        return {}

    a = asset_row.iloc[0]
    install_date = pd.to_datetime(a["install_date"])
    criticality = int(a["criticality"])
    replacement_cost = float(a["replacement_cost"])

    age_years = (reference_date - install_date).days / 365.25
    age_norm = _clamp(age_years / MAX_ASSET_LIFE_YEARS)

    # recent failures in last 12 months
    asset_events = events[events["asset_id"] == asset_id]
    failures_12mo = len(
        asset_events[
            (asset_events["event_type"] == "failure")
            & (asset_events["event_date"] >= reference_date - pd.Timedelta(days=365))
        ]
    )
    recent_fail_norm = _clamp(failures_12mo / MAX_RECENT_FAILURES)

    # overdue maintenance
    maint = asset_events[asset_events["event_type"] == "maintenance"]
    if not maint.empty:
        days_since = (reference_date - maint["event_date"].max()).days
    else:
        days_since = int((reference_date - install_date).days)
    overdue_norm = _clamp(days_since / OVERDUE_DAYS)

    # condition from latest readings
    asset_readings = readings[readings["asset_id"] == asset_id]
    if not asset_readings.empty:
        latest = asset_readings.sort_values("reading_date").iloc[-1]
        vib_norm = _clamp(latest["vibration_mm_s"] / VIBRATION_THRESHOLD)
        tmp_norm = _clamp(latest["temperature_c"] / TEMP_THRESHOLD)
        condition_norm = (vib_norm + tmp_norm) / 2.0
    else:
        condition_norm = 0.5

    pf_score = (
        0.35 * age_norm
        + 0.30 * recent_fail_norm
        + 0.20 * overdue_norm
        + 0.15 * condition_norm
    )
    prob_failure = _clamp(pf_score)
    consequence = (criticality / 5.0) * replacement_cost
    risk = prob_failure * consequence

    # top drivers
    drivers: list[str] = []
    components = {
        "age": (age_norm, 0.35),
        "recent_failures": (recent_fail_norm, 0.30),
        "overdue_maintenance": (overdue_norm, 0.20),
        "condition": (condition_norm, 0.15),
    }
    weighted = {k: v[0] * v[1] for k, v in components.items()}
    for driver, _ in sorted(weighted.items(), key=lambda x: -x[1]):
        if weighted[driver] > 0.05:
            drivers.append(driver)

    return {
        "asset_id": asset_id,
        "age_norm": round(age_norm, 3),
        "recent_fail_norm": round(recent_fail_norm, 3),
        "overdue_norm": round(overdue_norm, 3),
        "condition_norm": round(condition_norm, 3),
        "pf_score": round(pf_score, 3),
        "prob_failure": round(prob_failure, 3),
        "consequence": round(consequence, 2),
        "risk": round(risk, 2),
        "top_drivers": drivers,
    }


def compute_fleet_risk(
    assets: pd.DataFrame,
    events: pd.DataFrame,
    readings: pd.DataFrame,
    reference_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Compute risk for all assets in the fleet.

    Args:
        assets: Assets DataFrame.
        events: Events DataFrame.
        readings: Readings DataFrame.
        reference_date: Date to treat as "today".

    Returns:
        DataFrame with one row per asset and risk columns.
    """
    rows = []
    for asset_id in assets["asset_id"]:
        result = compute_risk_for_asset(
            asset_id, assets, events, readings, reference_date
        )
        if result:
            rows.append(result)
    df = pd.DataFrame(rows)
    return df.sort_values("risk", ascending=False).reset_index(drop=True)


def add_risk_bucket(risk_df: pd.DataFrame) -> pd.DataFrame:
    """Add a *risk_level* column (Low / Medium / High / Critical).

    Args:
        risk_df: DataFrame output of :func:`compute_fleet_risk`.

    Returns:
        DataFrame with an added ``risk_level`` column.
    """
    df = risk_df.copy()
    max_risk = df["risk"].max() if not df.empty else 1.0

    def _bucket(r: float) -> str:
        ratio = r / max_risk if max_risk > 0 else 0
        if ratio < 0.25:
            return "Low"
        if ratio < 0.50:
            return "Medium"
        if ratio < 0.75:
            return "High"
        return "Critical"

    df["risk_level"] = df["risk"].apply(_bucket)
    return df
