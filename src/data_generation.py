"""Synthetic data generation for the Asset Performance Analytics Dashboard."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEED = 42
N_PUMPS = 100
START_DATE = pd.Timestamp("2019-01-01")
END_DATE = pd.Timestamp("2023-12-31")

PUMP_TYPES = ["Centrifugal", "Submersible", "Axial Flow", "Mixed Flow"]
MANUFACTURERS = ["AquaTech", "FlowMaster", "HydroCore", "PumpPro"]
ZONES = ["Zone A", "Zone B", "Zone C", "Zone D", "Zone E"]
FAILURE_MODES = ["bearing", "seal", "cavitation", "motor", "clogging"]


def generate_assets(n: int = N_PUMPS, seed: int = SEED) -> pd.DataFrame:
    """Generate the *assets* table with pump metadata.

    Args:
        n: Number of pumps to generate.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with one row per pump.
    """
    rng = np.random.default_rng(seed)
    random.seed(seed)

    install_dates = [
        START_DATE - pd.Timedelta(days=int(d))
        for d in rng.integers(0, 365 * 15, n)
    ]

    return pd.DataFrame(
        {
            "asset_id": [f"PUMP-{i+1:03d}" for i in range(n)],
            "pump_type": rng.choice(PUMP_TYPES, n),
            "install_date": install_dates,
            "manufacturer": rng.choice(MANUFACTURERS, n),
            "model": [
                f"M-{rng.integers(100, 999)}" for _ in range(n)
            ],
            "site": [f"Site-{rng.integers(1, 11)}" for _ in range(n)],
            "zone": rng.choice(ZONES, n),
            "criticality": rng.integers(1, 6, n),
            "replacement_cost": rng.integers(15_000, 120_001, n),
            "capacity_gpm": rng.integers(50, 501, n),
        }
    )


def _degradation_factor(runtime_hours: float, age_years: float) -> float:
    """Return a multiplicative degradation factor based on age and runtime."""
    return 1.0 + 0.003 * age_years + 0.00002 * runtime_hours


def generate_readings(assets: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """Generate monthly sensor readings with simulated degradation.

    Vibration and temperature drift upward with age and runtime; maintenance
    events reset condition toward baseline.

    Args:
        assets: The assets DataFrame produced by :func:`generate_assets`.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame of monthly readings.
    """
    rng = np.random.default_rng(seed)
    rows = []

    months = pd.date_range(START_DATE, END_DATE, freq="MS")

    for _, asset in assets.iterrows():
        install_date: pd.Timestamp = asset["install_date"]
        capacity_gpm: float = float(asset["capacity_gpm"])
        cumulative_runtime = 0.0
        reset_month: int | None = None  # index of last maintenance

        for m_idx, month in enumerate(months):
            if month < install_date:
                continue

            age_years = (month - install_date).days / 365.25
            monthly_runtime = float(rng.uniform(600, 740))
            cumulative_runtime += monthly_runtime

            deg = _degradation_factor(cumulative_runtime, age_years)

            # maintenance resets condition partially
            if reset_month is not None and (m_idx - reset_month) < 3:
                deg = max(deg * 0.6, 1.0)

            flow = capacity_gpm * rng.uniform(0.80, 1.02) / deg
            pressure = rng.uniform(30.0, 80.0)
            power = rng.uniform(5.0, 50.0) * deg
            vibration = rng.uniform(1.0, 3.0) * deg + rng.normal(0, 0.1)
            temperature = rng.uniform(35.0, 55.0) * deg + rng.normal(0, 0.5)

            # simulate occasional maintenance resets
            if rng.random() < 0.05:
                reset_month = m_idx

            rows.append(
                {
                    "asset_id": asset["asset_id"],
                    "reading_date": month,
                    "runtime_hours": round(monthly_runtime, 1),
                    "flow_gpm": round(max(flow, 0), 1),
                    "pressure_psi": round(pressure, 1),
                    "power_kw": round(power, 2),
                    "vibration_mm_s": round(max(vibration, 0.1), 3),
                    "temperature_c": round(max(temperature, 20.0), 2),
                }
            )

    return pd.DataFrame(rows)


def generate_events(
    assets: pd.DataFrame,
    readings: pd.DataFrame,
    seed: int = SEED,
) -> pd.DataFrame:
    """Generate maintenance, inspection, and failure events.

    - Maintenance every 90-180 days (some missed).
    - Failures probabilistically based on age, overdue maintenance, and
      condition thresholds.

    Args:
        assets: Assets DataFrame.
        readings: Readings DataFrame.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame of events with one row per event.
    """
    rng = np.random.default_rng(seed)
    rows = []
    event_id = 1

    for _, asset in assets.iterrows():
        asset_id = asset["asset_id"]
        install_date: pd.Timestamp = asset["install_date"]
        criticality: int = int(asset["criticality"])

        asset_readings = readings[readings["asset_id"] == asset_id].sort_values(
            "reading_date"
        )
        if asset_readings.empty:
            continue

        # -- maintenance events --
        current = max(install_date, START_DATE)
        while current < END_DATE:
            interval_days = int(rng.integers(90, 181))
            # miss some maintenance
            if rng.random() < 0.15:
                interval_days = int(interval_days * rng.uniform(1.5, 2.5))
            current = current + pd.Timedelta(days=interval_days)
            if current >= END_DATE:
                break

            rows.append(
                {
                    "event_id": event_id,
                    "asset_id": asset_id,
                    "event_date": current,
                    "event_type": "maintenance",
                    "failure_mode": "none",
                    "downtime_hours": round(float(rng.uniform(2.0, 8.0)), 1),
                    "labor_hours": round(float(rng.uniform(2.0, 6.0)), 1),
                    "maintenance_cost": round(float(rng.uniform(300.0, 2500.0)), 2),
                    "notes": "Scheduled maintenance",
                }
            )
            event_id += 1

        # -- failure events --
        for _, row in asset_readings.iterrows():
            age_years = (row["reading_date"] - install_date).days / 365.25
            vibration = row["vibration_mm_s"]
            temperature = row["temperature_c"]

            # compute failure probability
            age_factor = min(age_years / 15.0, 1.0)
            cond_factor = min((vibration / 8.0 + temperature / 90.0) / 2.0, 1.0)
            fail_prob = 0.005 + 0.010 * age_factor + 0.015 * cond_factor
            fail_prob *= criticality / 5.0

            if rng.random() < fail_prob:
                mode = rng.choice(FAILURE_MODES)
                downtime = float(rng.uniform(4.0, 48.0))
                rows.append(
                    {
                        "event_id": event_id,
                        "asset_id": asset_id,
                        "event_date": row["reading_date"]
                        + pd.Timedelta(days=int(rng.integers(1, 28))),
                        "event_type": "failure",
                        "failure_mode": mode,
                        "downtime_hours": round(downtime, 1),
                        "labor_hours": round(float(rng.uniform(4.0, 16.0)), 1),
                        "maintenance_cost": round(float(rng.uniform(1000.0, 15000.0)), 2),
                        "notes": f"Unplanned failure: {mode}",
                    }
                )
                event_id += 1

        # -- inspection events (quarterly) --
        current = max(install_date, START_DATE)
        while current < END_DATE:
            current = current + pd.Timedelta(days=90)
            if current >= END_DATE:
                break
            rows.append(
                {
                    "event_id": event_id,
                    "asset_id": asset_id,
                    "event_date": current,
                    "event_type": "inspection",
                    "failure_mode": "none",
                    "downtime_hours": 0.5,
                    "labor_hours": round(float(rng.uniform(0.5, 2.0)), 1),
                    "maintenance_cost": round(float(rng.uniform(100.0, 400.0)), 2),
                    "notes": "Routine inspection",
                }
            )
            event_id += 1

    df = pd.DataFrame(rows)
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.normalize()
    return df.sort_values(["asset_id", "event_date"]).reset_index(drop=True)


def save_csvs(
    assets: pd.DataFrame,
    readings: pd.DataFrame,
    events: pd.DataFrame,
    output_dir: str = "data",
) -> None:
    """Save DataFrames to CSV files in *output_dir*.

    Args:
        assets: Assets DataFrame.
        readings: Readings DataFrame.
        events: Events DataFrame.
        output_dir: Directory path for output files.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    assets.to_csv(f"{output_dir}/assets.csv", index=False)
    readings.to_csv(f"{output_dir}/readings.csv", index=False)
    events.to_csv(f"{output_dir}/events.csv", index=False)
    print(f"CSVs saved to {output_dir}/")


if __name__ == "__main__":
    print("Generating synthetic data ...")
    assets_df = generate_assets()
    readings_df = generate_readings(assets_df)
    events_df = generate_events(assets_df, readings_df)
    save_csvs(assets_df, readings_df, events_df)
    print(
        f"Done: {len(assets_df)} assets, "
        f"{len(readings_df)} readings, "
        f"{len(events_df)} events."
    )
