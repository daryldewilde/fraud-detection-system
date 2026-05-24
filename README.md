# Explainable Fraud Detection System

Production-ready fraud detection platform with authentication, analysis history, and explainable risk scoring.

## What This Project Does

The system analyzes transaction data and detects suspicious behavior by combining:

- Rule checks
- Pattern checks
- Anomaly detection
- Weighted risk scoring
- Plain-language explanations

It is designed for analysts, operations teams, and compliance users.

## Features

### Core Detection
- CSV/XLSX ingestion with validation and cleaning
- Per-agent, per-hour feature engineering
- Multi-layer detection:
  - Rule-based signals (velocity, failure ratio, service concentration)
  - Sequence/pattern checks (cashout then quick movement, repeated similar-amount chains)
  - Isolation Forest anomaly detection
- Risk score in range `[0, 1]`
- Human-readable reasons and investigation details

### User Management and History
- Admin-created user accounts
- First-login password change enforcement
- Password hashing with bcrypt
- SQLite persistence of analyses
- Re-download of original input files and reports
- Analysis history with filtering, sorting, and pagination
- User attribution and timestamps for audit trails

## Project Structure

```
fraud-detection-system/
├── app.py
├── fraud_detection.db
├── .env
├── requirements.txt
├── src/
│   ├── auth.py
│   ├── config.py
│   ├── data_loader.py
│   ├── database.py
│   ├── detection.py
│   ├── explainability.py
│   ├── feature_engineering.py
│   ├── file_manager.py
│   ├── patterns.py
│   ├── scoring.py
│   └── utils.py
├── data/
│   ├── csv/
│   ├── excel/
│   └── uploads/user_*/
├── outputs/
│   └── reports/user_*/
└── tests/
```

## Environment Configuration

Configuration is now centralized in `.env`.

### `.env` keys
- `FRAUD_DETECTION_ADMIN_EMAIL`: seeded admin email
- `FRAUD_DETECTION_ADMIN_PASSWORD`: seeded admin password

Example (already created in this repo):

```env
FRAUD_DETECTION_ADMIN_EMAIL=admin@fraud.local
FRAUD_DETECTION_ADMIN_PASSWORD=Admin@12345
```

## Setup

Install dependencies:

```bash
pip install --break-system-packages -r requirements.txt
```

Run app:

```bash
streamlit run app.py
```

Run tests:

```bash
pytest -q
```

## End-to-End Workflow

### Authentication and Session
1. Seeded admin logs in.
2. Admin creates user accounts.
3. New users are forced to change password at first login.
4. Session identity is attached to actions.

### Analysis Workflow
1. Upload transaction file (CSV/XLSX).
2. Data is cleaned and normalized.
3. Hourly features are computed by agent.
4. Fraud detection layers run.
5. Risk score is computed.
6. Human-readable explanations are generated.
7. Results are displayed and exportable.
8. Analysis can be saved with file/report paths and metrics.

### History Workflow
1. Open Analysis History.
2. Filter by user/date.
3. Review newest-to-oldest records.
4. Page through records.
5. Download input/report and inspect details.

## Input Schema

Input file must include:

- `Agent`
- `Service`
- `Amount`
- `Status`
- `Paid At`

## Data Cleaning

Normalization pipeline:

1. Map aliases to canonical columns.
2. Normalize service casing.
3. Normalize status casing.
4. Coerce amount to numeric.
5. Parse timestamp.
6. Remove rows missing required fields.
7. Remove negative amounts.
8. Sort by event time.

## Feature Engineering (Per Agent, Per Hour)

For each `(Agent, hour)` window:

- `tx_count`
- `success_count`
- `fail_count`
- `fail_ratio`
- `avg_amount`
- `max_amount`

Formulas:

- $tx\_count = N$
- $success\_count = \sum 1[Status=SUCCESS]$
- $fail\_count = \sum 1[Status\neq SUCCESS]$
- $fail\_ratio = fail\_count / tx\_count$
- $avg\_amount = \frac{1}{N}\sum Amount$
- $max\_amount = \max(Amount)$

## Detection Layers

### Layer A: Rule-Based
Default checks:

- Velocity: `tx_count >= velocity_threshold` (default `50`)
- Failure ratio: `fail_ratio >= failure_ratio_threshold` (default `0.35`)
- Service concentration: `dominant_service_ratio >= service_concentration_threshold` (default `0.9`)

### Layer B: Pattern-Based
- Cashout followed by quick cashin/transfer with similar amount
- Repeated similar-amount chains

### Layer C: Anomaly Detection
Isolation Forest on:

- `tx_count`
- `success_count`
- `fail_count`
- `fail_ratio`
- `avg_amount`
- `max_amount`

Defaults:

- Contamination: `0.08`
- Minimum rows: `12`

## Risk Scoring

Default weights:

- Velocity: `0.30`
- Failure: `0.30`
- Anomaly: `0.40`
- Pattern: `0.20`
- Service concentration: `0.15`

Formula:

$$
risk = (velocity\_flag\times0.30)
+ (failure\_flag\times0.30)
+ (anomaly\_flag\times0.40)
+ (pattern\_flag\times0.20)
+ (service\_distribution\_flag\times0.15)
$$

Then clipped to `[0, 1]`.

Suspicious decision:

- `is_suspicious = (risk > risk_threshold)`
- Default `risk_threshold = 0.6`

## Output and Auditability

Report fields include:

- Agent
- Time
- Risk level
- Reason
- Key details

Audit support:

- User attribution (`user_id` and analyzer email)
- Timestamps
- Original input retention
- Report retention and linkage to analysis records

## Database Overview

### `users`
- `id`
- `email`
- `password_hash`
- `created_at`
- `is_active`
- `role`
- `force_password_change`

### `analyses`
- `id`
- `user_id`
- `analyzer_email`
- `filename`
- `input_file_path`
- `report_file_path`
- `results_json`
- `created_at`
- `total_rows`
- `suspicious_count`
- `avg_risk_score`

## Security Notes

Implemented:

- Bcrypt password hashing
- User-scoped access checks
- Session-based authentication
- File path ownership model

Future enhancements:

- Rate limiting
- Session timeout policies
- Extended audit event logs
- Encryption at rest

## Troubleshooting

`ModuleNotFoundError: sqlalchemy` or `dotenv`:

```bash
pip install --break-system-packages -r requirements.txt
```

`Database is locked`:

- Stop duplicate app processes
- Restart Streamlit app

Cannot log in:

- Verify admin credentials in `.env`
- Re-run app to trigger DB init and admin seed
