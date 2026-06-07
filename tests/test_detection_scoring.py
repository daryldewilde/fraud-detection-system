"""Unit tests for fraud detection and risk scoring pipeline."""

import pandas as pd

from src.config import FraudConfig
from src.detection import run_fraud_detection


def test_detection_pipeline_flags_velocity_and_failure() -> None:
    rows = []
    for idx in range(12):
        rows.append(
            {
                "Agent": "A1",
                "Service": "cashout",
                "Amount": 100 + idx,
                "Status": "FAILED" if idx < 8 else "SUCCESS",
                "Paid At": pd.Timestamp("2026-01-01 10:00:00") + pd.Timedelta(minutes=idx),
            }
        )

    df = pd.DataFrame(rows)

    cfg = FraudConfig(
        velocity_threshold=10,
        failure_ratio_threshold=0.5,
        risk_threshold=0.4,
        minimum_transactions_for_anomaly=999,
    )

    report = run_fraud_detection(df, config=cfg, enable_anomaly=False)
    first = report.iloc[0]

    assert bool(first["velocity_flag"]) is True
    assert bool(first["failure_flag"]) is True
    assert bool(first["service_distribution_flag"]) is True
    # velocity + failure + service concentration = 0.3 + 0.3 + 0.15 = 0.75;
    # anomaly not applied so total weight = 1.35 - 0.4 = 0.95
    assert abs(float(first["risk_score"]) - (0.75 / 0.95)) < 1e-9
    assert bool(first["is_suspicious"]) is True
    assert "High transaction velocity" in first["reasons"]


def test_detection_pipeline_pattern_reason_present() -> None:
    df = pd.DataFrame(
        {
            "Agent": ["A2", "A2"],
            "Service": ["cashout", "cashin"],
            "Amount": [1000, 1010],
            "Status": ["SUCCESS", "SUCCESS"],
            "Paid At": pd.to_datetime(["2026-01-01 09:00:00", "2026-01-01 09:03:00"]),
        }
    )

    cfg = FraudConfig(velocity_threshold=50, failure_ratio_threshold=0.9, minimum_transactions_for_anomaly=999)

    report = run_fraud_detection(df, config=cfg, enable_anomaly=False)
    row = report.iloc[0]

    assert bool(row["pattern_flag"]) is True
    assert "cashout" in row["reasons"].lower()


def test_detection_pipeline_skips_anomaly_when_disabled() -> None:
    df = pd.DataFrame(
        {
            "Agent": ["A4", "A4"],
            "Service": ["cashout", "cashout"],
            "Amount": [100, 101],
            "Status": ["SUCCESS", "SUCCESS"],
            "Paid At": pd.to_datetime(["2026-01-01 11:00:00", "2026-01-01 11:05:00"]),
        }
    )

    cfg = FraudConfig(minimum_transactions_for_anomaly=999)

    report = run_fraud_detection(df, config=cfg, enable_anomaly=False)
    row = report.iloc[0]

    assert bool(row["anomaly_flag"]) is False
    assert bool(row["anomaly_applied"]) is False
    assert "Anomalous behavior" not in row["reasons"]


def test_pattern_detection_avoids_false_positive_on_non_repeating_amounts() -> None:
    df = pd.DataFrame(
        {
            "Agent": ["A3"] * 10,
            "Service": ["cashin"] * 10,
            "Amount": [100 + i for i in range(10)],
            "Status": ["SUCCESS"] * 10,
            "Paid At": pd.to_datetime([f"2026-01-01 12:{i:02d}:00" for i in range(10)]),
        }
    )

    cfg = FraudConfig(
        velocity_threshold=100,
        failure_ratio_threshold=0.9,
        repeated_chain_min_count=3,
        minimum_transactions_for_anomaly=999,
    )

    report = run_fraud_detection(df, config=cfg, enable_anomaly=False)
    row = report.iloc[0]

    assert bool(row["pattern_flag"]) is False
