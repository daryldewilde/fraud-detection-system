"""Risk scoring logic for combining fraud signals."""

import pandas as pd

from .config import FraudConfig


def compute_risk_scores(df: pd.DataFrame, config: FraudConfig) -> pd.DataFrame:
    """Compute normalized risk score and suspicious classification."""
    scored = df.copy()

    weighted_sum = (
        scored["velocity_flag"].astype(float) * config.velocity_weight
        + scored["failure_flag"].astype(float) * config.failure_weight
        + scored["anomaly_flag"].astype(float) * config.anomaly_weight
        + scored["pattern_flag"].astype(float) * config.pattern_weight
        + scored["service_distribution_flag"].astype(float) * config.service_distribution_weight
    )

    base_total_weight = (
        config.velocity_weight
        + config.failure_weight
        + config.anomaly_weight
        + config.pattern_weight
        + config.service_distribution_weight
    )

    if base_total_weight <= 0:
        raise ValueError("At least one risk weight must be positive.")

    if "anomaly_applied" in scored.columns:
        anomaly_applied = scored["anomaly_applied"].fillna(False).astype(bool)
    else:
        anomaly_applied = pd.Series(True, index=scored.index)

    total_weight = base_total_weight - (~anomaly_applied).astype(float) * config.anomaly_weight
    total_weight = total_weight.where(total_weight > 0)

    scored["risk_score"] = weighted_sum / total_weight
    scored["risk_score"] = scored["risk_score"].fillna(0.0)
    scored["is_suspicious"] = scored["risk_score"] > config.risk_threshold

    return scored
