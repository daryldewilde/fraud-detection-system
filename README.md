# Explainable Fraud Detection System

This project is a production-quality prototype for fintech fraud detection with explainability and auditability.

## Features

- Data ingestion from CSV and XLSX exports
- Data normalization and validation
- Per-agent, per-hour feature engineering
- Multi-layered fraud detection:
  - Rule-based signals (velocity, failure ratio, service concentration)
  - Pattern detection (cashout -> immediate cashin/transfer, repeated similar-amount chains)
  - Isolation Forest anomaly detection
- Weighted risk scoring in range [0, 1]
- Human-readable explanations and metric details for each detection
- Streamlit dashboard with report download (Excel and PDF)

## Project Structure

- app.py: Streamlit dashboard
- src/: Core modules
- tests/: Unit tests
- data/csv/: CSV sample and input files
- data/excel/: XLSX sample and input files
- outputs/: Generated outputs (optional)

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Input Schema

Input CSV/XLSX must include:

- Agent
- Service (cashin, cashout, airtime, transfer, etc.)
- Amount
- Status (SUCCESS / FAILED)
- Paid At (timestamp)

## Output Report

Generated report columns:

- Agent
- hour (time window)
- is_suspicious
- risk_score
- reasons
- details

This output is suitable for audit and compliance workflows.

Export formats from the UI:

- Excel (.xlsx)
- PDF (.pdf)

## Test

```bash
pytest -q
```

## Project Documentation

- Full workflow and calculation guide: [PROJECT_WORKFLOW_AND_CALCULATIONS.md](PROJECT_WORKFLOW_AND_CALCULATIONS.md)

## Design Notes

- Configuration values are centralized in `src/config.py`
- Explainability is implemented in `src/explainability.py`
- The pipeline orchestration is implemented in `src/detection.py`
