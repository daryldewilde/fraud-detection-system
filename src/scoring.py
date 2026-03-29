"""Risk scoring logic for combining fraud signals."""

import numpy as np
import pandas as pd

from .config import FraudConfig


def compute_risk_scores(df: pd.DataFrame, config: FraudConfig) -> pd.DataFrame:
    """Compute weighted risk score and suspicious classification."""
    scored = df.copy()

    scored["risk_score"] = (
        scored["velocity_flag"].astype(float) * config.velocity_weight
        + scored["failure_flag"].astype(float) * config.failure_weight
        + scored["anomaly_flag"].astype(float) * config.anomaly_weight
        + scored["pattern_flag"].astype(float) * config.pattern_weight
        + scored["service_distribution_flag"].astype(float) * config.service_distribution_weight
    )

    scored["risk_score"] = np.clip(scored["risk_score"], 0.0, 1.0)
    scored["is_suspicious"] = scored["risk_score"] > config.risk_threshold

    return scored
