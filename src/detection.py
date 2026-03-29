"""Fraud detection orchestration: rules, patterns, anomaly, and scoring."""

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from .config import FraudConfig
from .explainability import build_explanations
from .feature_engineering import compute_hourly_agent_features, compute_service_distribution
from .patterns import detect_transaction_patterns
from .scoring import compute_risk_scores


def _apply_rule_flags(features: pd.DataFrame, config: FraudConfig) -> pd.DataFrame:
    """Apply deterministic rule-based fraud flags."""
    flagged = features.copy()
    flagged["velocity_flag"] = flagged["tx_count"] >= config.velocity_threshold
    flagged["failure_flag"] = flagged["fail_ratio"] >= config.failure_ratio_threshold
    flagged["service_distribution_flag"] = (
        flagged.get("service_ratio", 0.0) >= config.service_concentration_threshold
    )
    return flagged


def _apply_anomaly_detection(
    feature_df: pd.DataFrame,
    config: FraudConfig,
    enabled: bool = True,
) -> pd.DataFrame:
    """Apply Isolation Forest and append anomaly outputs."""
    with_anomaly = feature_df.copy()

    with_anomaly["anomaly_flag"] = False
    with_anomaly["anomaly_score"] = 0.0

    if not enabled:
        return with_anomaly

    if len(with_anomaly) < config.minimum_transactions_for_anomaly:
        return with_anomaly

    model_features = [
        "tx_count",
        "success_count",
        "fail_count",
        "fail_ratio",
        "avg_amount",
        "max_amount",
    ]

    training_data = with_anomaly[model_features].fillna(0.0)

    model = IsolationForest(
        contamination=config.anomaly_contamination,
        random_state=42,
        n_estimators=200,
    )
    predictions = model.fit_predict(training_data)
    raw_scores = model.decision_function(training_data)

    with_anomaly["anomaly_flag"] = predictions == -1
    with_anomaly["anomaly_score"] = np.clip(-raw_scores, 0.0, None)

    return with_anomaly


def run_fraud_detection(
    clean_transactions: pd.DataFrame,
    config: Optional[FraudConfig] = None,
    enable_anomaly: bool = True,
) -> pd.DataFrame:
    """Run complete fraud detection and return explainable scored report."""
    cfg = config or FraudConfig()

    features = compute_hourly_agent_features(clean_transactions)
    service_dist = compute_service_distribution(clean_transactions)
    patterns = detect_transaction_patterns(clean_transactions, cfg)

    merged = features.merge(service_dist, on=["Agent", "hour"], how="left")
    merged = merged.merge(patterns, on=["Agent", "hour"], how="left")

    merged["service_ratio"] = merged["service_ratio"].fillna(0.0)
    merged["pattern_flag"] = merged["pattern_flag"].eq(True)
    merged["pattern_count"] = pd.to_numeric(merged["pattern_count"], errors="coerce").fillna(0).astype(int)
    merged["pattern_reasons"] = merged["pattern_reasons"].fillna("")

    with_rules = _apply_rule_flags(merged, cfg)
    with_anomaly = _apply_anomaly_detection(with_rules, cfg, enabled=enable_anomaly)
    scored = compute_risk_scores(with_anomaly, cfg)
    explained = build_explanations(scored)

    report_cols = [
        "Agent",
        "hour",
        "is_suspicious",
        "risk_score",
        "reasons",
        "details",
        "tx_count",
        "success_count",
        "fail_count",
        "fail_ratio",
        "avg_amount",
        "max_amount",
        "velocity_flag",
        "failure_flag",
        "service_distribution_flag",
        "pattern_flag",
        "anomaly_flag",
    ]

    return explained[report_cols].sort_values(["risk_score", "Agent", "hour"], ascending=[False, True, True])
