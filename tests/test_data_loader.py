"""Unit tests for data loading and validation."""

from io import StringIO

import pandas as pd
import pytest

from src.data_loader import load_transactions, validate_and_clean_data


def test_validate_and_clean_data_normalizes_columns() -> None:
    df = pd.DataFrame(
        {
            "agent_id": ["A1", "A2"],
            "transaction_type": ["CashIn", "cashout"],
            "value": [100, 200],
            "result": ["success", "FAILED"],
            "timestamp": ["2026-01-01 10:00:00", "2026-01-01 10:05:00"],
        }
    )

    cleaned = validate_and_clean_data(df)

    assert list(cleaned.columns) == ["Agent", "Service", "Amount", "Status", "Paid At"]
    assert cleaned["Service"].tolist() == ["cashin", "cashout"]
    assert cleaned["Status"].tolist() == ["SUCCESS", "FAILED"]


def test_load_transactions_csv_file_object() -> None:
    csv_data = StringIO(
        "Agent,Service,Amount,Status,Paid At\n"
        "A1,cashin,100,SUCCESS,2026-01-01 09:00:00\n"
        "A1,cashout,50,FAILED,2026-01-01 09:05:00\n"
    )
    csv_data.name = "sample.csv"

    loaded = load_transactions(csv_data)

    assert len(loaded) == 2
    assert loaded["Amount"].sum() == 150


def test_validate_raises_missing_columns() -> None:
    df = pd.DataFrame({"Agent": ["A1"]})

    with pytest.raises(ValueError):
        validate_and_clean_data(df)
