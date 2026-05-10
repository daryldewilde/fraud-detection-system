"""Streamlit interface for the Explainable Fraud Detection System."""

from datetime import datetime
import secrets

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from src.auth import (
    init_session_state,
    login_page,
    logout,
    require_auth,
    get_current_user_id,
    get_current_user_email,
    get_current_user_role,
    must_change_password,
    password_change_page,
)
from src.config import FraudConfig
from src.data_loader import load_transactions
from src.database import init_db, create_analysis, get_user_analyses, create_user, get_user_by_email
from src.detection import run_fraud_detection
from src.feature_engineering import compute_hourly_agent_features
from src.file_manager import init_storage, save_uploaded_file, save_report_file, get_file_bytes, file_exists, get_filename_from_path
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


# Initialize database and storage on startup
init_db()
init_storage()
init_session_state()

# Page config
st.set_page_config(page_title="Explainable Fraud Detection System", layout="wide")

# Check authentication
if not require_auth():
    login_page()
    st.stop()

if must_change_password():
    password_change_page()
    st.stop()

# Authenticated user - show main app
st.title("Fraud Detection System")
st.caption("Production-grade fraud detection with analysis history and audit trails.")

# Sidebar: User info and logout
with st.sidebar:
    st.markdown("---")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.caption(f"Logged in as: **{get_current_user_email()}**")
    with col2:
        if st.button("Logout", use_container_width=True):
            logout()
    st.markdown("---")

    if get_current_user_role() == "admin":
        st.subheader("Admin Panel")
        with st.expander("Create user account", expanded=False):
            new_user_email = st.text_input("User Email", key="admin_new_user_email")
            temporary_password = st.text_input("Temporary Password (optional)", key="admin_temp_password")
            if not temporary_password:
                st.caption("Leave blank to auto-generate a one-time password when creating the user.")

            if st.button("Create User", use_container_width=True):
                if not new_user_email:
                    st.error("Enter an email address")
                elif get_user_by_email(new_user_email):
                    st.error("That email already exists")
                else:
                    try:
                        generated_password = temporary_password or secrets.token_urlsafe(10)
                        created_user = create_user(
                            new_user_email,
                            generated_password,
                            role="user",
                            force_password_change=True,
                        )
                        st.success(f"Created user: {created_user.email}")
                        st.info("They will be prompted to change their password on first login.")
                        st.code(generated_password)
                    except Exception as exc:
                        st.error(f"Could not create user: {exc}")

# Tabs for different sections
tab1, tab2 = st.tabs(["New Analysis", "Analysis History"])

with tab1:
    st.markdown(
        """
    ### How to use
    1. **Upload file** using the uploader below.
    2. **Adjust settings** in the left sidebar.
    3. **View results and download fraud report** from the tables below.
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
            # Save uploaded file
            input_file_path = save_uploaded_file(get_current_user_id(), uploaded_file)
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

    st.subheader("Download fraud report and save analysis")

    report_for_export = results_table.rename(
        columns={
            "Time": "Time",
            "Risk level (0-1)": "Risk level",
        }
    ).copy()
    report_for_export["Time"] = report_for_export["Time"].astype(str)

    col_excel, col_pdf = st.columns(2)

    with col_excel:
        excel_data = dataframe_to_excel_bytes(report_for_export)
        st.download_button(
            label="Download Report (Excel)",
            data=excel_data,
            file_name=f"fraud_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col_pdf:
        pdf_data = dataframe_to_pdf_bytes(report_for_export)
        st.download_button(
            label="Download Report (PDF)",
            data=pdf_data,
            file_name=f"fraud_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf",
        )

    # Save analysis to database
    if st.button("Save This Analysis", use_container_width=True):
        try:
            # Save report files
            excel_bytes = dataframe_to_excel_bytes(report_for_export)
            report_path = save_report_file(get_current_user_id(), 0, excel_bytes, "xlsx")

            # Create analysis record
            results_dict = report.to_dict(orient="records")
            analysis = create_analysis(
                user_id=get_current_user_id(),
                analyzer_email=get_current_user_email(),
                filename=uploaded_file.name,
                input_file_path=input_file_path,
                results_df=results_dict,
                total_rows=len(transactions),
                suspicious_count=int(display_report["is_suspicious"].sum()),
                avg_risk_score=float(display_report["risk_score"].mean()),
            )

            # Update report path
            from src.database import update_analysis_report
            update_analysis_report(analysis.id, report_path)

            st.success(f"Analysis saved — ID: {analysis.id}")
            st.balloons()
        except Exception as e:
            st.error(f"Error saving analysis: {str(e)}")

    st.subheader("What this means")
    st.markdown(
        """
    - Agents are flagged when their activity looks risky based on your settings.
    - **Risk level** is a number from 0 to 1. Higher means more risk.
    - Start by reviewing the highest risk rows, then check the reason and key details columns.
    - If needed, lower or raise settings in the sidebar and run again.
    """
    )

with tab2:
    st.header("Analysis History")
    st.markdown("View, download, and manage your past analyses.")

    user_id = get_current_user_id()
    analyses = get_user_analyses(user_id)

    if not analyses:
        st.info("No analyses yet. Go to the 'New Analysis' tab to create one.")
    else:
        st.markdown(f"Found **{len(analyses)}** analysis records")

        for analysis in analyses:
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    st.markdown(f"**{analysis.filename}**")
                    st.caption(f"Analyzed: {analysis.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    if analysis.analyzer_email:
                        st.caption(f"Analyzer: {analysis.analyzer_email}")

                    if analysis.total_rows:
                        st.markdown(
                            f"{analysis.total_rows} transactions | "
                            f"{analysis.suspicious_count} flagged | "
                            f"Avg risk: {analysis.avg_risk_score:.2f}"
                        )

                with col2:
                    st.markdown("**Downloads**")
                    
                    # Download input file
                    if file_exists(analysis.input_file_path):
                        try:
                            file_bytes = get_file_bytes(analysis.input_file_path)
                            st.download_button(
                                label="Input File",
                                data=file_bytes,
                                file_name=get_filename_from_path(analysis.input_file_path),
                                key=f"input_{analysis.id}",
                            )
                        except Exception as e:
                            st.error(f"Error loading file: {str(e)}")
                    else:
                        st.warning("Input file not found")

                with col3:
                    st.markdown("**Report**")
                    
                    # Download report
                    if analysis.report_file_path and file_exists(analysis.report_file_path):
                        try:
                            file_bytes = get_file_bytes(analysis.report_file_path)
                            st.download_button(
                                label="Report",
                                data=file_bytes,
                                file_name=get_filename_from_path(analysis.report_file_path),
                                key=f"report_{analysis.id}",
                            )
                        except Exception as e:
                            st.error(f"Error loading report: {str(e)}")
                    else:
                        st.warning("Report not ready")

                # Expandable results details
                with st.expander(f"View full results (Analysis #{analysis.id})"):
                    if analysis.results_json:
                        results_data = analysis.get_results()
                        results_df = pd.DataFrame(results_data)
                        st.dataframe(results_df, use_container_width=True)
                    else:
                        st.info("No results data available")

