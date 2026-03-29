"""Detection of sequential and repeated suspicious transaction patterns."""

from datetime import timedelta

import pandas as pd

from .config import FraudConfig


def detect_transaction_patterns(df: pd.DataFrame, config: FraudConfig) -> pd.DataFrame:
    """Detect suspicious patterns and return per-agent-hour flags with reasons."""
    working = df.sort_values(["Agent", "Paid At"]).copy()
    working["hour"] = working["Paid At"].dt.floor("h")

    records = []

    for agent, agent_df in working.groupby("Agent"):
        rows = agent_df.reset_index(drop=True)

        for idx in range(len(rows) - 1):
            current = rows.iloc[idx]
            nxt = rows.iloc[idx + 1]

            if current["Service"] != "cashout":
                continue

            time_gap = nxt["Paid At"] - current["Paid At"]
            amount_ratio = 0
            if current["Amount"] > 0:
                amount_ratio = nxt["Amount"] / current["Amount"]

            if (
                nxt["Service"] in {"cashin", "transfer"}
                and timedelta(minutes=0) <= time_gap <= timedelta(minutes=config.pattern_window_minutes)
                and 0.9 <= amount_ratio <= 1.1
            ):
                records.append(
                    {
                        "Agent": agent,
                        "hour": current["hour"],
                        "pattern_type": "cashout_followed_by_cashin_transfer",
                        "pattern_count": 1,
                        "pattern_reason": "Cashout followed by immediate cashin/transfer with similar amount",
                    }
                )

    repeated = (
        working.assign(amount_bucket=working["Amount"].round(2))
        .groupby(["Agent", "hour", "Service", "amount_bucket"])["Amount"]
        .count()
        .rename("repeat_count")
        .reset_index()
    )

    repeated = repeated[repeated["repeat_count"] >= config.repeated_chain_min_count]

    for _, row in repeated.iterrows():
        records.append(
            {
                "Agent": row["Agent"],
                "hour": row["hour"],
                "pattern_type": "repeated_similar_amount_chain",
                "pattern_count": int(row["repeat_count"]),
                "pattern_reason": "Repeated transaction chain with similar amounts",
            }
        )

    if not records:
        return pd.DataFrame(
            columns=["Agent", "hour", "pattern_flag", "pattern_count", "pattern_reasons"]
        )

    pattern_df = pd.DataFrame(records)
    result = (
        pattern_df.groupby(["Agent", "hour"], as_index=False)
        .agg(
            pattern_count=("pattern_count", "sum"),
            pattern_reasons=("pattern_reason", lambda x: "; ".join(sorted(set(x)))),
        )
        .assign(pattern_flag=True)
    )

    return result
