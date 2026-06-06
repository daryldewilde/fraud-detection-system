"""Streamlit interface for the Explainable Fraud Detection System."""

from datetime import datetime, timedelta
import secrets
import math

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
from src.database import (
    init_db,
    create_analysis,
    create_user,
    get_user_by_email,
    get_all_users,
    get_filtered_analyses,
)
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

    if isinstance(reason_text, (list, tuple, set)):
        raw_parts = [str(item).strip() for item in reason_text if str(item).strip()]
    else:
        normalized = str(reason_text).replace("[", "").replace("]", "").replace("'", "")
        raw_parts = [p.strip() for p in normalized.split(";") if p.strip()]

    parts = []
    for item in raw_parts:
        for piece in item.split(","):
            cleaned = piece.strip()
            if cleaned:
                parts.append(cleaned)
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


def risk_color_style(value: float) -> str:
    """Return background style for risk score display."""
    try:
        risk_value = float(value)
    except (TypeError, ValueError):
        return ""

    if risk_value >= 0.75:
        return "background-color: #fde2e2; color: #8b0000;"
    if risk_value >= 0.4:
        return "background-color: #fff1dc; color: #a15c00;"
    return "background-color: #e7f7ee; color: #0f5132;"


TABLE_BORDER_STYLES = [
    {"selector": "table", "props": [("border-collapse", "collapse"), ("width", "100%"), ("border", "1px solid #d1d5db")]},
    {"selector": "th", "props": [("border", "1px solid #d1d5db"), ("padding", "0.5rem"), ("background-color", "#f8fafc")]},
    {"selector": "td", "props": [("border", "1px solid #d1d5db"), ("padding", "0.5rem")]},
]


def bordered_styler(styler):
    """Apply consistent table borders to pandas Styler objects."""
    return styler.set_table_styles(TABLE_BORDER_STYLES, overwrite=False)


def inject_table_border_css() -> None:
    """Inject CSS so Streamlit-rendered tables and row grids show visible borders."""
    st.markdown(
        """
        <style>
        div[data-testid="stTable"] table {
            border-collapse: collapse !important;
            width: 100% !important;
        }
        div[data-testid="stTable"] th,
        div[data-testid="stTable"] td {
            border: 1px solid #d1d5db !important;
            padding: 0.5rem !important;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            border-right: 1px solid #d1d5db;
            border-bottom: 1px solid #d1d5db;
            padding: 0.15rem 0.35rem; /* tighter vertical spacing for history rows */
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
            border-left: 1px solid #d1d5db;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def build_display_report(report: pd.DataFrame) -> pd.DataFrame:
    """Create the display-friendly fraud report used by the UI."""
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
    return display_report


def render_analysis_bundle(transactions: pd.DataFrame, report: pd.DataFrame, include_save: bool = True) -> None:
    """Render the complete analysis results bundle: summary, table, charts, and downloads."""
    display_report = build_display_report(report)

    st.session_state.analysis_display_report_df = display_report.copy()

    st.divider()
    st.subheader("4. Results")

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
    st.dataframe(bordered_styler(summary_df.style), use_container_width=True, hide_index=True)

    st.markdown("#### Fraud results table")
    st.caption("These are the most suspicious cases based on risk score")

    filtered = display_report[display_report["is_suspicious"]].copy().sort_values(by="risk_score", ascending=False)
    if filtered.empty:
        st.warning("No suspicious activity detected")
        filtered = filtered.copy()

    results_table = filtered[["Agent", "hour", "risk_score", "Reason", "Key details"]].rename(
        columns={
            "hour": "Time",
            "risk_score": "Risk level (0-1)",
        }
    )

    styled_results_table = results_table.style.map(
        risk_color_style,
        subset=["Risk level (0-1)"],
    )
    st.dataframe(bordered_styler(styled_results_table), use_container_width=True)

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
        plt.close(fig)

    with col2:
        st.subheader("Failed Transaction Share")
        feature_df = compute_hourly_agent_features(transactions)
        fig2, ax2 = plt.subplots(figsize=(7, 4))
        ax2.hist(feature_df["fail_ratio"], bins=20, color="#d62728", edgecolor="black")
        ax2.set_xlabel("Failed transaction share")
        ax2.set_ylabel("Count of Agent-Hour Windows")
        ax2.set_title("Failed Transaction Share Distribution")
        st.pyplot(fig2)
        plt.close(fig2)

    st.subheader("Download fraud report")

    report_for_export = results_table.rename(
        columns={
            "Time": "Time",
            "Risk level (0-1)": "Risk level",
        }
    ).copy()
    report_for_export["Time"] = report_for_export["Time"].astype(str)
    st.session_state.analysis_report_for_export_df = report_for_export.copy()

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

    if include_save:
        if st.button("Save This Analysis", use_container_width=True):
            try:
                excel_bytes = dataframe_to_excel_bytes(report_for_export)
                user_id = get_current_user_id() or getattr(st.session_state, "user_id", None)
                filename = getattr(st.session_state, "uploaded_filename", None) or "unknown"

                report_path = save_report_file(user_id or 0, 0, excel_bytes, "xlsx")
                results_dict = report.to_dict(orient="records")
                analysis = create_analysis(
                    user_id=user_id,
                    analyzer_email=get_current_user_email(),
                    filename=filename,
                    input_file_path=getattr(st.session_state, "input_file_path", ""),
                    results_df=results_dict,
                    total_rows=len(transactions),
                    suspicious_count=int(display_report["is_suspicious"].sum()),
                    avg_risk_score=float(display_report["risk_score"].mean()),
                )

                from src.database import update_analysis_report

                update_analysis_report(analysis.id, report_path)

                st.success(f"Analysis saved — ID: {analysis.id}")
                st.balloons()
            except Exception as e:
                import traceback

                tb = traceback.format_exc()
                try:
                    from pathlib import Path

                    logp = Path("outputs") / "error_log.txt"
                    logp.parent.mkdir(parents=True, exist_ok=True)
                    with open(logp, "a") as lf:
                        lf.write(f"[{datetime.now().isoformat()}] Error saving analysis:\n")
                        lf.write(tb + "\n")
                except Exception:
                    pass
                st.error("Error saving analysis. See server logs for details.")
                st.exception(e)

    st.subheader("What this means")
    st.markdown(
        """
    - Agents are flagged when their activity looks risky based on your settings.
    - **Risk level** is a number from 0 to 1. Higher means more risk.
    - Start by reviewing the highest risk rows, then check the reason and key details columns.
    - If needed, lower or raise settings in the sidebar and run again.
    """
    )


# Initialize database and storage on startup
init_db()
init_storage()
init_session_state()

# Page config
st.set_page_config(page_title="Explainable Fraud Detection System", layout="wide")
inject_table_border_css()

# Check authentication
if not require_auth():
    login_page()
    st.stop()

if must_change_password():
    password_change_page()
    st.stop()

# Authenticated user - show main app
st.title("Fraud Detection System")
st.caption(
    "Analyze transaction files, detect suspicious activity, and manage analysis history in one place."
)
st.markdown("")

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
    st.subheader("1. Upload Data")
    st.caption("Start by uploading a transaction history export in CSV or Excel format.")

    with st.sidebar:
        st.header("Settings")
        st.caption("Adjust detection behavior before running the analysis.")

        st.subheader("Preset")
        # Preset profiles that map to sensible default control values
        preset_defaults = {
            "Balanced": {
                "velocity_threshold": 50,
                "failure_ratio_threshold": 0.35,
                "risk_threshold": 0.6,
                "service_concentration_threshold": 0.9,
                "enable_anomaly": True,
            },
            "Conservative": {
                "velocity_threshold": 20,
                "failure_ratio_threshold": 0.15,
                "risk_threshold": 0.75,
                "service_concentration_threshold": 0.95,
                "enable_anomaly": False,
            },
            "Aggressive": {
                "velocity_threshold": 120,
                "failure_ratio_threshold": 0.45,
                "risk_threshold": 0.45,
                "service_concentration_threshold": 0.8,
                "enable_anomaly": True,
            },
        }

        selected_preset = st.radio(
            "Profile",
            options=["Balanced", "Conservative", "Aggressive"],
            index=0,
            help="Preset is a guidance label for your workflow. Threshold controls below remain fully manual.",
        )

        # Initialize or update session state values when preset changes
        if "preset_selected" not in st.session_state:
            st.session_state.preset_selected = selected_preset
        if st.session_state.preset_selected != selected_preset:
            # apply defaults from selected preset into session_state so sliders update
            defaults = preset_defaults.get(selected_preset, {})
            for k, v in defaults.items():
                st.session_state[k] = v
            st.session_state.preset_selected = selected_preset
        if selected_preset == "Conservative":
            st.caption("Conservative: lower false positives, stricter flagging.")
        elif selected_preset == "Aggressive":
            st.caption("Aggressive: broader detection, may flag more cases.")
        else:
            st.caption("Balanced: standard sensitivity for day-to-day analysis.")

        st.subheader("Detection sensitivity")

        velocity_threshold = st.slider(
            "Max transactions per hour",
            min_value=5,
            max_value=500,
            value=st.session_state.get(
                "velocity_threshold", preset_defaults[selected_preset]["velocity_threshold"]
            ),
            key="velocity_threshold",
            help="Flag activity when one agent has more than this number of transactions in an hour.",
        )
        failure_ratio_threshold = st.slider(
            "Failed transactions limit",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.get(
                "failure_ratio_threshold", preset_defaults[selected_preset]["failure_ratio_threshold"]
            ),
            key="failure_ratio_threshold",
            step=0.01,
            help="Flag activity when the failed transaction share is above this limit.",
        )
        risk_threshold = st.slider(
            "Risk level to flag",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.get(
                "risk_threshold", preset_defaults[selected_preset]["risk_threshold"]
            ),
            key="risk_threshold",
            step=0.01,
            help="Cases above this risk level are marked as suspicious.",
        )

        with st.expander("Optional advanced checks"):
            service_concentration_threshold = st.slider(
                "Same transaction type limit",
                min_value=0.5,
                max_value=1.0,
                value=st.session_state.get(
                    "service_concentration_threshold",
                    preset_defaults[selected_preset]["service_concentration_threshold"],
                ),
                key="service_concentration_threshold",
                step=0.01,
                help="Flag activity when almost all transactions are the same type.",
            )
            enable_anomaly = st.checkbox(
                "Detect unusual activity",
                value=st.session_state.get(
                    "enable_anomaly", preset_defaults[selected_preset]["enable_anomaly"]
                ),
                key="enable_anomaly",
                help="Uses an additional check to find behavior that looks unusual.",
            )

    uploaded_file = st.file_uploader(
        "Upload transactions file (CSV or XLSX)",
        type=["csv", "xlsx"],
        help="Upload a transaction history file exported from the application (CSV or Excel).",
    )

    if uploaded_file is None:
        st.info("Please upload a file to start analysis")
    else:
        try:
            with st.spinner("Uploading file..."):
                transactions = load_transactions(uploaded_file)
                # Save uploaded file
                input_file_path = save_uploaded_file(get_current_user_id(), uploaded_file)
                # persist file info across reruns
                previous_filename = st.session_state.get("uploaded_filename")
                st.session_state.uploaded_filename = uploaded_file.name
                st.session_state.input_file_path = input_file_path
                if previous_filename != uploaded_file.name:
                    st.session_state.analysis_ready = False
        except Exception as exc:
            st.error(friendly_error_message(exc))
            st.stop()

        st.success("File loaded successfully")
        st.caption(f"Rows loaded: {len(transactions)}")
        st.divider()

        st.subheader("2. Configure Analysis")
        st.caption("Review a sample of uploaded data and confirm settings in the sidebar.")
        st.markdown("")

        st.markdown("#### File preview")
        st.dataframe(transactions.head(200), use_container_width=True)
        st.info("Use the sidebar controls to adjust how strict the checks should be.")

        st.divider()
        st.subheader("3. Run Analysis")
        run_analysis = st.button("Run Fraud Analysis", use_container_width=True, type="primary")

        analysis_ready = bool(st.session_state.get("analysis_ready"))

        if run_analysis:
            config = FraudConfig(
                velocity_threshold=velocity_threshold,
                failure_ratio_threshold=failure_ratio_threshold,
                service_concentration_threshold=service_concentration_threshold,
                risk_threshold=risk_threshold,
            )

            with st.spinner("Analyzing transactions..."):
                report = run_fraud_detection(transactions, config=config, enable_anomaly=enable_anomaly)

            st.success("Analysis complete. Results are ready below.")
            analysis_ready = True

            # persist results in session_state so Save works after reruns
            st.session_state.analysis_ready = True
            st.session_state.analysis_transactions_df = transactions.copy()
            st.session_state.analysis_report_df = report.copy()
            st.session_state.analysis_display_report_df = report.copy()
            st.session_state.analysis_report_for_export_df = None
        elif not analysis_ready:
            st.warning("Click 'Run Fraud Analysis' to process this file.")
            st.stop()

        if not run_analysis and analysis_ready:
            transactions = st.session_state.analysis_transactions_df.copy()
            report = st.session_state.analysis_report_df.copy()

        if "report" not in locals():
            st.stop()

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

        st.session_state.analysis_display_report_df = display_report.copy()
        st.session_state.analysis_report_for_export_df = None

        st.divider()
        st.subheader("4. Results")

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
        st.dataframe(bordered_styler(summary_df.style), use_container_width=True, hide_index=True)

        st.markdown("#### Fraud results table")
        st.caption("These are the most suspicious cases based on risk score")
        show_only_flagged = st.checkbox("Show only suspicious cases", value=True)
        min_risk_to_show = st.slider("Minimum risk level to show", 0.0, 1.0, 0.0, 0.01)

        filtered = display_report[display_report["risk_score"] >= min_risk_to_show].copy()
        if show_only_flagged:
            filtered = filtered[filtered["is_suspicious"]]

        filtered = filtered.sort_values(by="risk_score", ascending=False)

        if filtered.empty:
            st.warning("No suspicious activity detected")
            filtered = filtered.copy()

        results_table = filtered[["Agent", "hour", "risk_score", "Reason", "Key details"]].rename(
            columns={
                "hour": "Time",
                "risk_score": "Risk level (0-1)",
            }
        )

        styled_results_table = results_table.style.map(
            risk_color_style,
            subset=["Risk level (0-1)"],
        )
        st.dataframe(bordered_styler(styled_results_table), use_container_width=True)

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
        st.session_state.analysis_report_for_export_df = report_for_export.copy()

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
                # Rebuild export DataFrame if needed (protect against rerun state loss)
                if "report_for_export" not in locals():
                    try:
                        # Attempt to rebuild from display_report
                        report_for_export = (
                            display_report[["Agent", "hour", "risk_score", "reasons"]]
                            .rename(columns={"hour": "Time", "risk_score": "Risk level"})
                            .copy()
                        )
                        report_for_export["Time"] = report_for_export["Time"].astype(str)
                    except Exception:
                        raise RuntimeError("Could not reconstruct report for export. Please re-run the analysis and try again.")

                excel_bytes = dataframe_to_excel_bytes(report_for_export)

                user_id = get_current_user_id() or getattr(st.session_state, "user_id", None)
                filename = getattr(st.session_state, "uploaded_filename", None) or (
                    uploaded_file.name if "uploaded_file" in locals() and uploaded_file is not None else "unknown"
                )

                report_path = save_report_file(user_id or 0, 0, excel_bytes, "xlsx")

                # Create analysis record
                results_dict = report.to_dict(orient="records")
                analysis = create_analysis(
                    user_id=user_id,
                    analyzer_email=get_current_user_email(),
                    filename=filename,
                    input_file_path=getattr(st.session_state, "input_file_path", input_file_path if "input_file_path" in locals() else ""),
                    results_df=results_dict,
                    total_rows=(len(transactions) if "transactions" in locals() else None),
                    suspicious_count=int(display_report["is_suspicious"].sum()) if "display_report" in locals() else None,
                    avg_risk_score=float(display_report["risk_score"].mean()) if "display_report" in locals() else None,
                )

                # Update report path
                from src.database import update_analysis_report
                update_analysis_report(analysis.id, report_path)

                st.success(f"Analysis saved — ID: {analysis.id}")
                st.balloons()
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                # write to a log file for debugging
                try:
                    from pathlib import Path
                    logp = Path("outputs") / "error_log.txt"
                    logp.parent.mkdir(parents=True, exist_ok=True)
                    with open(logp, "a") as lf:
                        lf.write(f"[{datetime.now().isoformat()}] Error saving analysis:\n")
                        lf.write(tb + "\n")
                except Exception:
                    pass
                st.error("Error saving analysis. See server logs for details.")
                st.exception(e)

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
    st.subheader("5. History")
    st.caption("Review previous analyses, open details, and re-download reports.")

    user_id = get_current_user_id()
    current_role = get_current_user_role()

    # Filters
    with st.container(border=True):
        st.subheader("Filters")
        filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 2])

        selected_user_id = None
        with filter_col1:
            if current_role == "admin":
                users = get_all_users()
                user_options = {"All users": None}
                for u in users:
                    user_options[u.email] = u.id
                selected_user_label = st.selectbox(
                    "User",
                    options=list(user_options.keys()),
                    index=0,
                )
                selected_user_id = user_options[selected_user_label]
            else:
                st.text_input("User", value=str(get_current_user_email()), disabled=True)

        with filter_col2:
            date_preset = st.selectbox(
                "Quick date filter",
                options=["All dates", "Today", "Last 7 days", "Last 30 days"],
                index=0,
            )

        with filter_col3:
            date_range = st.date_input("Date range", value=())
            start_date = None
            end_date = None
            if isinstance(date_range, tuple):
                if len(date_range) == 2:
                    start_date, end_date = date_range
                elif len(date_range) == 1:
                    start_date = date_range[0]
                    end_date = date_range[0]
            else:
                start_date = date_range
                end_date = date_range

            today = datetime.now().date()
            if date_preset == "Today":
                start_date = today
                end_date = today
            elif date_preset == "Last 7 days":
                start_date = today - timedelta(days=6)
                end_date = today
            elif date_preset == "Last 30 days":
                start_date = today - timedelta(days=29)
                end_date = today

        page_size = 10

    # Count first to build proper pagination bounds
    _, total_count = get_filtered_analyses(
        requesting_user_id=user_id,
        requesting_user_role=current_role,
        filter_user_id=selected_user_id,
        start_date=start_date,
        end_date=end_date,
        page=1,
        page_size=1,
    )

    total_pages = max(1, math.ceil(total_count / page_size))

    current_page = min(max(1, int(st.session_state.get("history_page", 1))), total_pages)
    st.session_state.history_page = current_page

    analyses, _ = get_filtered_analyses(
        requesting_user_id=user_id,
        requesting_user_role=current_role,
        filter_user_id=selected_user_id,
        start_date=start_date,
        end_date=end_date,
        page=current_page,
        page_size=page_size,
    )

    if not analyses:
        st.info("No analyses yet. Go to the 'New Analysis' tab to create one.")
    else:
        selected_history_analysis_id = st.session_state.get("selected_history_analysis_id")
        start_idx = (current_page - 1) * page_size + 1
        end_idx = start_idx + len(analyses) - 1
        st.markdown(f"Showing **{start_idx}-{end_idx}** of **{total_count}** analysis records")

        history_rows = []
        analyses_by_id = {}
        for analysis in analyses:
            displayed_user = analysis.analyzer_email or (analysis.user.email if analysis.user else "Unknown")
            history_rows.append(
                {
                    "Analysis ID": analysis.id,
                    "Date": analysis.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "User": displayed_user,
                    "Transactions": int(analysis.total_rows or 0),
                    "Suspicious": int(analysis.suspicious_count or 0),
                    "Average Risk": round(float(analysis.avg_risk_score or 0.0), 3),
                    "File": analysis.filename,
                }
            )
            analyses_by_id[analysis.id] = analysis

        with st.container(border=True):
            header_cols = st.columns([1.2, 1.8, 2.2, 1.2, 1.2, 1.4, 1.1])
            header_cols[0].markdown("**Analysis ID**")
            header_cols[1].markdown("**Date**")
            header_cols[2].markdown("**User**")
            header_cols[3].markdown("**Transactions**")
            header_cols[4].markdown("**Suspicious**")
            header_cols[5].markdown("**Average Risk**")
            header_cols[6].markdown("**Action**")

            for index, row in enumerate(history_rows):
                analysis_id = row["Analysis ID"]
                if index > 0:
                    st.markdown('<hr style="margin:6px 0;border-top:1px solid #e5e7eb">', unsafe_allow_html=True)
                row_cols = st.columns([1.2, 1.8, 2.2, 1.2, 1.2, 1.4, 1.1])
                row_cols[0].write(row["Analysis ID"])
                row_cols[1].write(row["Date"])
                row_cols[2].write(row["User"])
                row_cols[3].write(row["Transactions"])
                row_cols[4].write(row["Suspicious"])
                row_cols[5].write(row["Average Risk"])
                if row_cols[6].button("Show Details", key=f"show_details_{analysis_id}", use_container_width=True):
                    st.session_state.selected_history_analysis_id = analysis_id
                    selected_history_analysis_id = analysis_id

        pagination_col1, pagination_col2 = st.columns([1, 2])
        with pagination_col1:
            st.selectbox("Page", options=list(range(1, total_pages + 1)), index=current_page - 1, key="history_page")
        with pagination_col2:
            st.caption(f"Showing newest first. Total records: {total_count}")

        selected_analysis = analyses_by_id.get(selected_history_analysis_id)

        if selected_analysis:
            st.divider()
            st.markdown("#### Selected analysis details")
            selected_user = selected_analysis.analyzer_email or (
                selected_analysis.user.email if selected_analysis.user else "Unknown"
            )
            st.caption(f"User: {selected_user}")
            st.caption(f"Analysis Date: {selected_analysis.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

            action_col1, action_col2 = st.columns(2)
            with action_col1:
                if selected_analysis.report_file_path and file_exists(selected_analysis.report_file_path):
                    try:
                        report_bytes = get_file_bytes(selected_analysis.report_file_path)
                        st.download_button(
                            label="Download Report",
                            data=report_bytes,
                            file_name=get_filename_from_path(selected_analysis.report_file_path),
                            key=f"download_report_{selected_analysis.id}",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"Error loading report: {str(e)}")
                else:
                    st.warning("Report not ready")

            with action_col2:
                if file_exists(selected_analysis.input_file_path):
                    try:
                        input_bytes = get_file_bytes(selected_analysis.input_file_path)
                        st.download_button(
                            label="Download Input File",
                            data=input_bytes,
                            file_name=get_filename_from_path(selected_analysis.input_file_path),
                            key=f"download_input_{selected_analysis.id}",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"Error loading input file: {str(e)}")
                else:
                    st.warning("Input file not found")

            if selected_analysis.results_json:
                try:
                    details_report = pd.DataFrame(selected_analysis.get_results())
                    saved_transactions = load_transactions(selected_analysis.input_file_path)
                    st.caption("Saved analysis rendered with the same summary, table, and charts as the original run.")
                    render_analysis_bundle(saved_transactions, details_report, include_save=False)
                except Exception as e:
                    st.error(f"Error showing details: {e}")
            else:
                st.info("No results data available")

