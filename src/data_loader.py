"""Data loading, normalization, and validation utilities."""

from pathlib import Path
from typing import IO, Union

import pandas as pd

CANONICAL_COLUMNS = {
    "agent": "Agent",
    "service": "Service",
    "amount": "Amount",
    "status": "Status",
    "paid_at": "Paid At",
}

COLUMN_ALIASES = {
    "agent": {"agent", "agent_id", "merchant", "operator"},
    "service": {"service", "transaction_type", "type", "channel"},
    "amount": {"amount", "value", "transaction_amount"},
    "status": {"status", "result", "state"},
    "paid_at": {"paid_at", "paid at", "timestamp", "created_at", "time"},
}


def _normalize_token(value: str) -> str:
    """Normalize a column token for robust matching."""
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Map supported aliases to canonical column names."""
    rename_map = {}

    for column in df.columns:
        token = _normalize_token(str(column))
        for canonical, aliases in COLUMN_ALIASES.items():
            if token in aliases:
                rename_map[column] = CANONICAL_COLUMNS[canonical]
                break

    return df.rename(columns=rename_map)


def _read_input_file(file_input: Union[str, Path, IO[bytes]]) -> pd.DataFrame:
    """Read transaction data from CSV or Excel input."""
    if hasattr(file_input, "name"):
        filename = str(getattr(file_input, "name", "")).lower()
        if filename.endswith(".xlsx"):
            return pd.read_excel(file_input)
        return pd.read_csv(file_input)

    path = Path(file_input)
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return pd.read_excel(path)
    if suffix == ".csv":
        return pd.read_csv(path)

    raise ValueError("Unsupported file format. Please upload a CSV or XLSX file.")


def validate_and_clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Validate schema and clean invalid values from transactions."""
    if df.empty:
        raise ValueError("Input dataset is empty.")

    normalized = normalize_column_names(df.copy())

    missing = [col for col in CANONICAL_COLUMNS.values() if col not in normalized.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    cleaned = normalized[list(CANONICAL_COLUMNS.values())].copy()

    cleaned["Agent"] = cleaned["Agent"].astype(str).str.strip()
    cleaned["Service"] = cleaned["Service"].astype(str).str.strip().str.lower()
    cleaned["Status"] = cleaned["Status"].astype(str).str.strip().str.upper()

    cleaned["Amount"] = pd.to_numeric(cleaned["Amount"], errors="coerce")
    cleaned["Paid At"] = pd.to_datetime(cleaned["Paid At"], errors="coerce", utc=False)

    cleaned = cleaned.dropna(subset=["Agent", "Service", "Amount", "Status", "Paid At"])
    cleaned = cleaned[cleaned["Amount"] >= 0]
    cleaned = cleaned[cleaned["Agent"] != ""]

    cleaned = cleaned.sort_values("Paid At").reset_index(drop=True)
    if cleaned.empty:
        raise ValueError("No valid records remain after cleaning.")

    return cleaned


def load_transactions(file_input: Union[str, Path, IO[bytes]]) -> pd.DataFrame:
    """Load and clean transaction records from a CSV or XLSX input."""
    raw = _read_input_file(file_input)
    return validate_and_clean_data(raw)
