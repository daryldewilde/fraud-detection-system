"""Unit tests for risk scoring logic."""

import pandas as pd

from src.config import FraudConfig
from src.scoring import compute_risk_scores


def test_compute_risk_scores_weighted_sum_and_threshold() -> None:
    df = pd.DataFrame(
        {
            "velocity_flag": [True, False],
            "failure_flag": [True, True],
            "anomaly_flag": [False, True],
            "pattern_flag": [True, False],
            "service_distribution_flag": [False, True],
        }
    )

    cfg = FraudConfig(
        velocity_weight=0.3,
        failure_weight=0.3,
        anomaly_weight=0.4,
        pattern_weight=0.2,
        service_distribution_weight=0.1,
        risk_threshold=0.7,
    )

    scored = compute_risk_scores(df, cfg)

    assert abs(scored.iloc[0]["risk_score"] - 0.8) < 1e-9
    assert bool(scored.iloc[0]["is_suspicious"]) is True

    assert abs(scored.iloc[1]["risk_score"] - 0.8) < 1e-9
    assert bool(scored.iloc[1]["is_suspicious"]) is True
