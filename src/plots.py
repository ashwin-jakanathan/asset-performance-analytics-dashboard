"""Plotly chart helpers for the Asset Performance Analytics Dashboard."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def failures_over_time_chart(failures_ts: pd.DataFrame) -> go.Figure:
    """Line chart of monthly failure counts.

    Args:
        failures_ts: DataFrame with ``period`` and ``failure_count`` columns.

    Returns:
        Plotly Figure.
    """
    fig = px.line(
        failures_ts,
        x="period",
        y="failure_count",
        title="Failures Over Time",
        labels={"period": "Month", "failure_count": "Failures"},
        markers=True,
    )
    fig.update_layout(hovermode="x unified")
    return fig


def risk_distribution_histogram(risk_df: pd.DataFrame) -> go.Figure:
    """Histogram of fleet risk scores.

    Args:
        risk_df: Fleet risk DataFrame with a ``risk`` column.

    Returns:
        Plotly Figure.
    """
    fig = px.histogram(
        risk_df,
        x="risk",
        nbins=20,
        title="Risk Score Distribution",
        labels={"risk": "Risk Score"},
        color_discrete_sequence=["#EF553B"],
    )
    return fig


def asset_timeline_chart(events: pd.DataFrame) -> go.Figure:
    """Scatter timeline of asset events coloured by event type.

    Args:
        events: Events DataFrame for a single asset.

    Returns:
        Plotly Figure.
    """
    color_map = {"failure": "#EF553B", "maintenance": "#00CC96", "inspection": "#636EFA"}
    fig = px.scatter(
        events,
        x="event_date",
        y="event_type",
        color="event_type",
        color_discrete_map=color_map,
        hover_data=["failure_mode", "downtime_hours", "maintenance_cost", "notes"],
        title="Event Timeline",
        labels={"event_date": "Date", "event_type": "Event Type"},
    )
    fig.update_traces(marker_size=10)
    return fig


def sensor_line_chart(readings: pd.DataFrame, column: str, title: str) -> go.Figure:
    """Line chart for a sensor reading column over time.

    Args:
        readings: Readings DataFrame for a single asset.
        column: Column name to plot.
        title: Chart title.

    Returns:
        Plotly Figure.
    """
    fig = px.line(
        readings,
        x="reading_date",
        y=column,
        title=title,
        labels={"reading_date": "Date", column: column},
        markers=False,
    )
    return fig


def risk_by_zone_chart(risk_df: pd.DataFrame, assets: pd.DataFrame) -> go.Figure:
    """Bar chart of average risk score by zone.

    Args:
        risk_df: Fleet risk DataFrame.
        assets: Assets DataFrame.

    Returns:
        Plotly Figure.
    """
    merged = risk_df.merge(assets[["asset_id", "zone"]], on="asset_id")
    zone_risk = merged.groupby("zone")["risk"].mean().reset_index()
    zone_risk.columns = ["zone", "avg_risk"]
    fig = px.bar(
        zone_risk.sort_values("avg_risk", ascending=False),
        x="zone",
        y="avg_risk",
        title="Average Risk by Zone",
        labels={"zone": "Zone", "avg_risk": "Average Risk Score"},
        color="avg_risk",
        color_continuous_scale="Reds",
    )
    return fig


def risk_by_age_bucket_chart(
    risk_df: pd.DataFrame, assets: pd.DataFrame, reference_date: pd.Timestamp
) -> go.Figure:
    """Bar chart of average risk by age bucket.

    Args:
        risk_df: Fleet risk DataFrame.
        assets: Assets DataFrame.
        reference_date: Date to compute ages against.

    Returns:
        Plotly Figure.
    """
    merged = risk_df.merge(assets[["asset_id", "install_date"]], on="asset_id")
    merged["age_years"] = (
        reference_date - pd.to_datetime(merged["install_date"])
    ).dt.days / 365.25
    merged["age_bucket"] = pd.cut(
        merged["age_years"],
        bins=[0, 3, 6, 10, 15, 100],
        labels=["0-3 yr", "3-6 yr", "6-10 yr", "10-15 yr", "15+ yr"],
    )
    bucket_risk = merged.groupby("age_bucket", observed=True)["risk"].mean().reset_index()
    fig = px.bar(
        bucket_risk,
        x="age_bucket",
        y="risk",
        title="Average Risk by Age Bucket",
        labels={"age_bucket": "Age Bucket", "risk": "Average Risk Score"},
        color="risk",
        color_continuous_scale="Oranges",
    )
    return fig


def failures_by_mode_pareto(events: pd.DataFrame) -> go.Figure:
    """Pareto chart of failures by failure mode.

    Args:
        events: Events DataFrame.

    Returns:
        Plotly Figure.
    """
    failures = events[events["event_type"] == "failure"].copy()
    mode_counts = (
        failures.groupby("failure_mode").size().reset_index(name="count")
    ).sort_values("count", ascending=False)
    mode_counts["cumulative_pct"] = (
        mode_counts["count"].cumsum() / mode_counts["count"].sum() * 100
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=mode_counts["failure_mode"],
            y=mode_counts["count"],
            name="Failure Count",
            marker_color="#636EFA",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=mode_counts["failure_mode"],
            y=mode_counts["cumulative_pct"],
            name="Cumulative %",
            yaxis="y2",
            line_color="#EF553B",
        )
    )
    fig.update_layout(
        title="Failures by Failure Mode (Pareto)",
        yaxis={"title": "Failure Count"},
        yaxis2={"title": "Cumulative %", "overlaying": "y", "side": "right", "range": [0, 110]},
        hovermode="x unified",
    )
    return fig


def age_vs_risk_bubble(
    risk_df: pd.DataFrame,
    assets: pd.DataFrame,
    reference_date: pd.Timestamp,
) -> go.Figure:
    """Bubble scatter of age vs. risk score, sized by criticality.

    Args:
        risk_df: Fleet risk DataFrame.
        assets: Assets DataFrame.
        reference_date: Date to compute ages against.

    Returns:
        Plotly Figure.
    """
    merged = risk_df.merge(
        assets[["asset_id", "install_date", "criticality", "zone"]], on="asset_id"
    )
    merged["age_years"] = (
        reference_date - pd.to_datetime(merged["install_date"])
    ).dt.days / 365.25
    fig = px.scatter(
        merged,
        x="age_years",
        y="risk",
        size="criticality",
        color="zone",
        hover_name="asset_id",
        title="Age vs. Risk Score (bubble = criticality)",
        labels={"age_years": "Age (years)", "risk": "Risk Score"},
    )
    return fig
