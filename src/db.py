"""Database connection helpers and query functions for the pump dashboard."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pandas as pd

DB_PATH = Path("database/pumps.db")


@contextmanager
def get_connection(db_path: Path = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields an SQLite connection.

    Args:
        db_path: Path to the SQLite database file.

    Yields:
        An open ``sqlite3.Connection``.

    Raises:
        FileNotFoundError: If the database file does not exist.
    """
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found at {db_path}. "
            "Run `python -m src.data_generation` then `python -m src.etl` first."
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def query_df(sql: str, params: tuple = (), db_path: Path = DB_PATH) -> pd.DataFrame:
    """Execute *sql* and return the result as a DataFrame.

    Args:
        sql: SQL query string.
        params: Tuple of parameters for parameterised queries.
        db_path: Path to the SQLite database.

    Returns:
        Result as a pandas DataFrame.
    """
    with get_connection(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def get_all_assets(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return the full *assets* table.

    Args:
        db_path: Path to the SQLite database.

    Returns:
        DataFrame with one row per asset.
    """
    return query_df("SELECT * FROM assets ORDER BY asset_id", db_path=db_path)


def get_all_readings(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return the full *readings* table with dates parsed.

    Args:
        db_path: Path to the SQLite database.

    Returns:
        DataFrame of sensor readings.
    """
    df = query_df(
        "SELECT * FROM readings ORDER BY asset_id, reading_date",
        db_path=db_path,
    )
    df["reading_date"] = pd.to_datetime(df["reading_date"])
    return df


def get_all_events(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return the full *events* table with dates parsed.

    Args:
        db_path: Path to the SQLite database.

    Returns:
        DataFrame of maintenance/failure events.
    """
    df = query_df(
        "SELECT * FROM events ORDER BY asset_id, event_date",
        db_path=db_path,
    )
    df["event_date"] = pd.to_datetime(df["event_date"])
    return df


def get_asset_readings(asset_id: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return sensor readings for a single asset.

    Args:
        asset_id: The asset identifier.
        db_path: Path to the SQLite database.

    Returns:
        DataFrame of readings for the given asset.
    """
    df = query_df(
        "SELECT * FROM readings WHERE asset_id = ? ORDER BY reading_date",
        params=(asset_id,),
        db_path=db_path,
    )
    df["reading_date"] = pd.to_datetime(df["reading_date"])
    return df


def get_asset_events(asset_id: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Return events for a single asset.

    Args:
        asset_id: The asset identifier.
        db_path: Path to the SQLite database.

    Returns:
        DataFrame of events for the given asset.
    """
    df = query_df(
        "SELECT * FROM events WHERE asset_id = ? ORDER BY event_date",
        params=(asset_id,),
        db_path=db_path,
    )
    df["event_date"] = pd.to_datetime(df["event_date"])
    return df
