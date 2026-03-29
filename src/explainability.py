"""Explainability utilities to produce human-readable fraud reasons."""

import pandas as pd


def build_explanations(df: pd.DataFrame) -> pd.DataFrame:
    """Build reasons and details fields for each scored row."""
    explained = df.copy()

    reason_texts = []
    detail_texts = []

    for _, row in explained.iterrows():
        reasons = []

        if row.get("velocity_flag", False):
            reasons.append("High transaction velocity")
        if row.get("failure_flag", False):
            reasons.append("High failure ratio")
        if row.get("service_distribution_flag", False):
            reasons.append("Suspicious service concentration")
        if row.get("pattern_flag", False):
            pattern_reasons = str(row.get("pattern_reasons", "")).strip()
            if pattern_reasons:
                reasons.append(pattern_reasons)
            else:
                reasons.append("Suspicious transaction chain pattern")
        if row.get("anomaly_flag", False):
            reasons.append("Anomalous behavior detected by Isolation Forest")

        if not reasons:
            reasons.append("No suspicious indicators triggered")

        details = (
            f"tx_count={int(row.get('tx_count', 0))}, "
            f"fail_ratio={float(row.get('fail_ratio', 0.0)):.2f}, "
            f"avg_amount={float(row.get('avg_amount', 0.0)):.2f}, "
            f"max_amount={float(row.get('max_amount', 0.0)):.2f}"
        )

        reason_texts.append("; ".join(reasons))
        detail_texts.append(details)

    explained["reasons"] = reason_texts
    explained["details"] = detail_texts

    return explained
