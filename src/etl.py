"""ETL: load CSV files into SQLite with basic validation."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DATA_DIR = Path("data")
DB_PATH = Path("database/pumps.db")

_CREATE_ASSETS = """
CREATE TABLE IF NOT EXISTS assets (
    asset_id          TEXT PRIMARY KEY,
    pump_type         TEXT NOT NULL,
    install_date      TEXT NOT NULL,
    manufacturer      TEXT NOT NULL,
    model             TEXT NOT NULL,
    site              TEXT NOT NULL,
    zone              TEXT NOT NULL,
    criticality       INTEGER NOT NULL,
    replacement_cost  REAL NOT NULL,
    capacity_gpm      REAL NOT NULL
);
"""

_CREATE_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    event_id          INTEGER PRIMARY KEY,
    asset_id          TEXT NOT NULL REFERENCES assets(asset_id),
    event_date        TEXT NOT NULL,
    event_type        TEXT NOT NULL,
    failure_mode      TEXT NOT NULL,
    downtime_hours    REAL NOT NULL DEFAULT 0,
    labor_hours       REAL NOT NULL DEFAULT 0,
    maintenance_cost  REAL NOT NULL DEFAULT 0,
    notes             TEXT
);
"""

_CREATE_READINGS = """
CREATE TABLE IF NOT EXISTS readings (
    asset_id          TEXT NOT NULL REFERENCES assets(asset_id),
    reading_date      TEXT NOT NULL,
    runtime_hours     REAL NOT NULL,
    flow_gpm          REAL NOT NULL,
    pressure_psi      REAL NOT NULL,
    power_kw          REAL NOT NULL,
    vibration_mm_s    REAL NOT NULL,
    temperature_c     REAL NOT NULL,
    PRIMARY KEY (asset_id, reading_date)
);
"""


def _validate_assets(df: pd.DataFrame) -> pd.DataFrame:
    """Validate assets DataFrame.

    Args:
        df: Raw assets DataFrame.

    Returns:
        Cleaned DataFrame.

    Raises:
        ValueError: If required columns are missing or data is invalid.
    """
    required = {
        "asset_id", "pump_type", "install_date", "manufacturer", "model",
        "site", "zone", "criticality", "replacement_cost", "capacity_gpm",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"assets CSV missing columns: {missing}")

    df = df.dropna(subset=["asset_id"]).copy()
    df["criticality"] = df["criticality"].astype(int).clip(1, 5)
    df["replacement_cost"] = pd.to_numeric(df["replacement_cost"], errors="coerce").fillna(0)
    df["capacity_gpm"] = pd.to_numeric(df["capacity_gpm"], errors="coerce").fillna(0)
    df["install_date"] = pd.to_datetime(df["install_date"]).dt.strftime("%Y-%m-%d")
    return df


def _validate_events(df: pd.DataFrame) -> pd.DataFrame:
    """Validate events DataFrame.

    Args:
        df: Raw events DataFrame.

    Returns:
        Cleaned DataFrame.
    """
    df = df.dropna(subset=["asset_id", "event_date"]).copy()
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.strftime("%Y-%m-%d")
    df["downtime_hours"] = pd.to_numeric(df["downtime_hours"], errors="coerce").fillna(0)
    df["labor_hours"] = pd.to_numeric(df["labor_hours"], errors="coerce").fillna(0)
    df["maintenance_cost"] = pd.to_numeric(df["maintenance_cost"], errors="coerce").fillna(0)
    return df


def _validate_readings(df: pd.DataFrame) -> pd.DataFrame:
    """Validate readings DataFrame.

    Args:
        df: Raw readings DataFrame.

    Returns:
        Cleaned DataFrame.
    """
    df = df.dropna(subset=["asset_id", "reading_date"]).copy()
    df["reading_date"] = pd.to_datetime(df["reading_date"]).dt.strftime("%Y-%m-%d")
    for col in ["runtime_hours", "flow_gpm", "pressure_psi", "power_kw",
                "vibration_mm_s", "temperature_c"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def load_to_sqlite(
    data_dir: Path = DATA_DIR,
    db_path: Path = DB_PATH,
) -> None:
    """Load validated CSVs into an SQLite database.

    Args:
        data_dir: Directory containing assets.csv, events.csv, readings.csv.
        db_path: Destination SQLite file path.

    Raises:
        FileNotFoundError: If any CSV file is missing.
    """
    for fname in ("assets.csv", "events.csv", "readings.csv"):
        fpath = data_dir / fname
        if not fpath.exists():
            raise FileNotFoundError(
                f"Missing {fpath}. Run `python -m src.data_generation` first."
            )

    db_path.parent.mkdir(parents=True, exist_ok=True)

    assets = _validate_assets(pd.read_csv(data_dir / "assets.csv"))
    events = _validate_events(pd.read_csv(data_dir / "events.csv"))
    readings = _validate_readings(pd.read_csv(data_dir / "readings.csv"))

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.executescript(_CREATE_ASSETS + _CREATE_EVENTS + _CREATE_READINGS)
        conn.commit()

        # truncate and reload
        cur.executescript("DELETE FROM readings; DELETE FROM events; DELETE FROM assets;")
        conn.commit()

        assets.to_sql("assets", conn, if_exists="append", index=False)
        events.to_sql("events", conn, if_exists="append", index=False)
        readings.to_sql("readings", conn, if_exists="append", index=False)
        conn.commit()
        print(
            f"Loaded {len(assets)} assets, {len(events)} events, "
            f"{len(readings)} readings into {db_path}."
        )
    finally:
        conn.close()


if __name__ == "__main__":
    load_to_sqlite()
