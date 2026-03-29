"""Streamlit interface for the Explainable Fraud Detection System."""

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from src.config import FraudConfig
from src.data_loader import load_transactions
from src.detection import run_fraud_detection
from src.feature_engineering import compute_hourly_agent_features
from src.utils import dataframe_to_excel_bytes, dataframe_to_pdf_bytes


def to_plain_reason(reason_text: str) -> str:
    """Convert technical reason strings into plain-language explanations."""
    reason_map = {
        "High transaction velocity": "too many transactions happened in a short time",
        "High failure ratio": "many transactions failed in this time period",
        "Suspicious service concentration": "most transactions were the same type",
        "Cashout followed by immediate cashin/transfer with similar amount": (
            "money was cashed out and quickly moved back in or transferred"
        ),
        "Repeated transaction chain with similar amounts": "very similar amounts were repeated many times",
        "Anomalous behavior detected by Isolation Forest": "the behavior is unusual compared with normal patterns",
        "No suspicious indicators triggered": "no unusual activity was found",
    }

    parts = [p.strip() for p in str(reason_text).split(";") if p.strip()]
    mapped = [reason_map.get(p, p.lower()) for p in parts]

    if not mapped:
        return "No unusual activity was found."

    if mapped == ["no unusual activity was found"]:
        return "No unusual activity was found."

    if len(mapped) == 1:
        return f"This case was flagged because {mapped[0]}."

    sentence = ", ".join(mapped[:-1]) + f", and {mapped[-1]}"
    return f"This case was flagged because {sentence}."


def friendly_error_message(exc: Exception) -> str:
    """Translate technical errors into user-friendly messages."""
    text = str(exc)
    if "Missing required columns" in text:
        return "Your file is missing required columns. Please check the template and try again."
    if "Unsupported file format" in text:
        return "Please upload a CSV or Excel (.xlsx) file."
    if "Input dataset is empty" in text:
        return "Your file is empty. Please upload a file with transaction data."
    if "No valid records remain" in text:
        return "We could not find valid rows after cleaning the file. Please review your data and try again."
    return "We could not read this file. Please check the format and required columns, then try again."


st.set_page_config(page_title="Explainable Fraud Detection System", layout="wide")
st.title("Simple Fraud Detection Tool")
st.caption("A simple business tool for finding suspicious transaction activity.")

st.markdown(
    """
### How to use this tool
1. **Step 1: Upload file** using the uploader below.
2. **Step 2: Adjust settings** in the left sidebar.
3. **Step 3: View results and download fraud report** from the tables below.
"""
)

with st.sidebar:
    st.header("Settings")
    st.subheader("Detection sensitivity")

    velocity_threshold = st.slider(
        "Max transactions per hour",
        min_value=5,
        max_value=500,
        value=50,
        help="Flag activity when one agent has more than this number of transactions in an hour.",
    )
    failure_ratio_threshold = st.slider(
        "Failed transactions limit",
        min_value=0.0,
        max_value=1.0,
        value=0.35,
        step=0.01,
        help="Flag activity when the failed transaction share is above this limit.",
    )
    risk_threshold = st.slider(
        "Risk level to flag",
        min_value=0.0,
        max_value=1.0,
        value=0.6,
        step=0.01,
        help="Cases above this risk level are marked as suspicious.",
    )

    with st.expander("Optional advanced checks"):
        service_concentration_threshold = st.slider(
            "Same transaction type limit",
            min_value=0.5,
            max_value=1.0,
            value=0.9,
            step=0.01,
            help="Flag activity when almost all transactions are the same type.",
        )
        pattern_weight = st.slider(
            "Repeated pattern impact",
            min_value=0.0,
            max_value=0.5,
            value=0.2,
            step=0.01,
            help="Increase this to give more weight to repeating transaction patterns.",
        )
        enable_anomaly = st.checkbox(
            "Detect unusual activity",
            value=True,
            help="Uses an additional check to find behavior that looks unusual.",
        )

st.subheader("Step 1: Upload file")
uploaded_file = st.file_uploader("Upload transactions file (CSV or XLSX)", type=["csv", "xlsx"])

if uploaded_file is None:
    st.info("Please upload a file to begin.")
    st.stop()

try:
    with st.spinner("Uploading file..."):
        transactions = load_transactions(uploaded_file)
except Exception as exc:
    st.error(friendly_error_message(exc))
    st.stop()

st.subheader("File preview")
st.dataframe(transactions.head(200), use_container_width=True)

st.subheader("Step 2: Adjust settings")
st.info("Use the left sidebar to adjust how strict the checks should be.")

config = FraudConfig(
    velocity_threshold=velocity_threshold,
    failure_ratio_threshold=failure_ratio_threshold,
    service_concentration_threshold=service_concentration_threshold,
    risk_threshold=risk_threshold,
    pattern_weight=pattern_weight,
)

with st.spinner("Analyzing transactions..."):
    report = run_fraud_detection(transactions, config=config, enable_anomaly=enable_anomaly)

st.success("Done! Results ready below.")

display_report = report.copy()
display_report["Reason"] = display_report["reasons"].apply(to_plain_reason)
display_report["Key details"] = display_report.apply(
    lambda row: (
        f"Transactions: {int(row['tx_count'])}, "
        f"Failed: {int(row['fail_count'])}, "
        f"Avg amount: {float(row['avg_amount']):.2f}, "
        f"Max amount: {float(row['max_amount']):.2f}"
    ),
    axis=1,
)

st.subheader("Step 3: View results")

st.markdown("#### Summary table")
summary_df = pd.DataFrame(
    [
        {
            "Total transactions": int(len(transactions)),
            "Suspicious cases": int(display_report["is_suspicious"].sum()),
            "Average risk level": round(float(display_report["risk_score"].mean()), 3),
        }
    ]
)
st.dataframe(summary_df, use_container_width=True, hide_index=True)

st.markdown("#### Fraud results table")
show_only_flagged = st.checkbox("Show only suspicious cases", value=True)
min_risk_to_show = st.slider("Minimum risk level to show", 0.0, 1.0, 0.0, 0.01)

filtered = display_report[display_report["risk_score"] >= min_risk_to_show].copy()
if show_only_flagged:
    filtered = filtered[filtered["is_suspicious"]]

results_table = filtered[["Agent", "hour", "risk_score", "Reason", "Key details"]].rename(
    columns={
        "hour": "Time",
        "risk_score": "Risk level (0-1)",
    }
)

st.dataframe(results_table, use_container_width=True)

st.markdown("#### Optional charts")
col1, col2 = st.columns(2)

with col1:
    st.subheader("Transaction amount distribution")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(transactions["Amount"], bins=30, color="#1f77b4", edgecolor="black")
    ax.set_xlabel("Amount")
    ax.set_ylabel("Frequency")
    ax.set_title("Transaction Distribution")
    st.pyplot(fig)

with col2:
    st.subheader("Failed Transaction Share")
    feature_df = compute_hourly_agent_features(transactions)
    fig2, ax2 = plt.subplots(figsize=(7, 4))
    ax2.hist(feature_df["fail_ratio"], bins=20, color="#d62728", edgecolor="black")
    ax2.set_xlabel("Failed transaction share")
    ax2.set_ylabel("Count of Agent-Hour Windows")
    ax2.set_title("Failed Transaction Share Distribution")
    st.pyplot(fig2)

st.subheader("Download fraud report")

report_for_export = results_table.rename(
    columns={
        "Time": "Time",
        "Risk level (0-1)": "Risk level",
    }
).copy()
report_for_export["Time"] = report_for_export["Time"].astype(str)

excel_data = dataframe_to_excel_bytes(report_for_export)
pdf_data = dataframe_to_pdf_bytes(report_for_export)

st.download_button(
    label="Download fraud report (Excel)",
    data=excel_data,
    file_name="fraud_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.download_button(
    label="Download fraud report (PDF)",
    data=pdf_data,
    file_name="fraud_report.pdf",
    mime="application/pdf",
)

st.subheader("What this means")
st.markdown(
    """
- Agents are flagged when their activity looks risky based on your settings.
- **Risk level** is a number from 0 to 1. Higher means more risk.
- Start by reviewing the highest risk rows, then check the reason and key details columns.
- If needed, lower or raise settings in the sidebar and run again.
"""
)
