"""Unit tests for risk scoring logic."""

import pandas as pd

from src.config import FraudConfig
from src.scoring import compute_risk_scores


def test_compute_risk_scores_weighted_sum_and_threshold() -> None:
    df = pd.DataFrame(
        {
            "velocity_flag": [True, False],
            "failure_flag": [True, False],
            "anomaly_flag": [False, True],
            "pattern_flag": [True, False],
            "service_distribution_flag": [False, False],
        }
    )

    cfg = FraudConfig(
        velocity_weight=0.3,
        failure_weight=0.3,
        anomaly_weight=0.4,
        pattern_weight=0.2,
        service_distribution_weight=0.1,
        risk_threshold=0.5,
    )

    scored = compute_risk_scores(df, cfg)

    assert abs(scored.iloc[0]["risk_score"] - (0.8 / 1.3)) < 1e-9
    assert bool(scored.iloc[0]["is_suspicious"]) is True

    assert abs(scored.iloc[1]["risk_score"] - (0.4 / 1.3)) < 1e-9
    assert bool(scored.iloc[1]["is_suspicious"]) is False


def test_compute_risk_scores_normalize_to_one_when_all_flags_true() -> None:
    df = pd.DataFrame(
        {
            "velocity_flag": [True],
            "failure_flag": [True],
            "anomaly_flag": [True],
            "pattern_flag": [True],
            "service_distribution_flag": [True],
        }
    )

    cfg = FraudConfig(
        velocity_weight=0.3,
        failure_weight=0.3,
        anomaly_weight=0.4,
        pattern_weight=0.2,
        service_distribution_weight=0.1,
        risk_threshold=0.95,
    )

    scored = compute_risk_scores(df, cfg)

    assert abs(scored.iloc[0]["risk_score"] - 1.0) < 1e-9
    assert bool(scored.iloc[0]["is_suspicious"]) is True
