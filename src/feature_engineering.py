"""Feature engineering for fraud detection signals."""

import pandas as pd


def compute_hourly_agent_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-agent, per-hour aggregated transactional features."""
    working = df.copy()
    working["hour"] = working["Paid At"].dt.floor("h")

    grouped = working.groupby(["Agent", "hour"], dropna=False)

    feature_df = grouped.agg(
        tx_count=("Amount", "count"),
        success_count=("Status", lambda s: (s == "SUCCESS").sum()),
        fail_count=("Status", lambda s: (s != "SUCCESS").sum()),
        avg_amount=("Amount", "mean"),
        max_amount=("Amount", "max"),
    ).reset_index()

    feature_df["fail_ratio"] = (
        feature_df["fail_count"] / feature_df["tx_count"].replace({0: 1})
    )

    return feature_df


def compute_service_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-agent, per-hour max service concentration ratio."""
    working = df.copy()
    working["hour"] = working["Paid At"].dt.floor("h")

    totals = (
        working.groupby(["Agent", "hour"]) ["Amount"]
        .count()
        .rename("tx_count")
        .reset_index()
    )

    service_counts = (
        working.groupby(["Agent", "hour", "Service"]) ["Amount"]
        .count()
        .rename("service_tx_count")
        .reset_index()
    )

    merged = service_counts.merge(totals, on=["Agent", "hour"], how="left")
    merged["service_ratio"] = merged["service_tx_count"] / merged["tx_count"].replace({0: 1})

    idx = merged.groupby(["Agent", "hour"])["service_ratio"].idxmax()
    dominant = merged.loc[idx, ["Agent", "hour", "Service", "service_ratio"]].copy()
    dominant = dominant.rename(columns={"Service": "dominant_service"})

    return dominant.reset_index(drop=True)
