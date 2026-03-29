"""Unit tests for engineered transaction features."""

import pandas as pd

from src.feature_engineering import compute_hourly_agent_features


def test_compute_hourly_agent_features() -> None:
    df = pd.DataFrame(
        {
            "Agent": ["A1", "A1", "A1", "A2"],
            "Service": ["cashin", "cashout", "cashout", "airtime"],
            "Amount": [100, 200, 300, 50],
            "Status": ["SUCCESS", "FAILED", "SUCCESS", "FAILED"],
            "Paid At": pd.to_datetime(
                [
                    "2026-01-01 10:01:00",
                    "2026-01-01 10:15:00",
                    "2026-01-01 10:35:00",
                    "2026-01-01 11:00:00",
                ]
            ),
        }
    )

    features = compute_hourly_agent_features(df)
    a1 = features[features["Agent"] == "A1"].iloc[0]

    assert a1["tx_count"] == 3
    assert a1["success_count"] == 2
    assert a1["fail_count"] == 1
    assert abs(a1["fail_ratio"] - (1 / 3)) < 1e-9
    assert a1["max_amount"] == 300
