"""Configuration models for fraud detection thresholds and weights."""

from dataclasses import dataclass


@dataclass
class FraudConfig:
    """Runtime configuration for fraud detection behavior."""

    velocity_threshold: int = 50
    failure_ratio_threshold: float = 0.35
    service_concentration_threshold: float = 0.9
    pattern_window_minutes: int = 10
    repeated_chain_min_count: int = 3
    anomaly_contamination: float = 0.08
    risk_threshold: float = 0.6

    velocity_weight: float = 0.3
    failure_weight: float = 0.3
    anomaly_weight: float = 0.4
    pattern_weight: float = 0.2
    service_distribution_weight: float = 0.15

    minimum_transactions_for_anomaly: int = 12
