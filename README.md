# Explainable Fraud Detection System

Production-ready fintech fraud detection platform with user authentication, analysis persistence, and audit trails.

## Features

**Core Detection:**
- Data ingestion from CSV and XLSX exports
- Data normalization and validation
- Per-agent, per-hour feature engineering
- Multi-layered fraud detection:
  - Rule-based signals (velocity, failure ratio, service concentration)
  - Pattern detection (cashout → immediate cashin/transfer, repeated similar-amount chains)
  - Isolation Forest anomaly detection
- Weighted risk scoring in range [0, 1]
- Human-readable explanations and metric details for each detection

**User Management & History (Phase 1):**
- Admin-created user accounts with email/password login
- Default admin account can create new users after login
- First-login password change required for newly created users
- Analysis persistence to SQLite database
- View complete history of all past analyses
- Re-download original input files
- Re-download generated reports (Excel/PDF)
- Audit trail with timestamps

## Project Structure

```
├── app.py                          # Main Streamlit app (auth + tabs)
├── fraud_detection.db              # SQLite database (auto-created)
├── requirements.txt                # Dependencies including sqlalchemy, bcrypt
│
├── src/
│   ├── database.py                 # SQLAlchemy models (User, Analysis)
│   ├── auth.py                     # Authentication & session management
│   ├── file_manager.py             # File storage (uploads + reports)
│   ├── detection.py                # Fraud detection engine
│   ├── feature_engineering.py      # Feature calculations
│   ├── scoring.py                  # Risk scoring
│   ├── explainability.py           # Explanation generation
│   ├── data_loader.py              # CSV/XLSX parsing
│   ├── patterns.py                 # Pattern detection
│   ├── config.py                   # Configuration
│   └── utils.py                    # Utilities
│
├── data/
│   ├── csv/                        # Sample CSVs
│   ├── excel/                      # Sample Excel files
│   └── uploads/user_*/             # User uploaded files (managed by app)
│
├── outputs/
│   └── reports/user_*/             # Generated reports (managed by app)
│
└── tests/                          # Unit tests
```

## Setup

1. Install dependencies:
```bash
pip install --break-system-packages -r requirements.txt
```

2. Database is auto-initialized on first run (SQLite, no setup needed).

## Run

```bash
streamlit run app.py
```

The app will:
1. Show a login page on first visit
2. Let the seeded admin sign in and create new users
3. Force first-time users to change their password on initial login
4. Preserve all analyses in database for future sessions

## Input Schema

Input CSV/XLSX must include:

- **Agent** - Transaction originator identifier
- **Service** - cashin, cashout, airtime, transfer, etc.
- **Amount** - Transaction value
- **Status** - SUCCESS or FAILED
- **Paid At** - Transaction timestamp

## Output Report

Generated report includes:

- Agent
- hour (time window)
- is_suspicious (true/false)
- risk_score (0-1 scale)
- reasons (plain-language explanation)
- details (metric breakdowns)

Export formats:
- Excel (.xlsx) - with formatting
- PDF (.pdf) - for compliance

All reports are saved to history for re-download.

## User Interface

### Tab 1: New Analysis
1. Upload CSV/XLSX file
2. Adjust sensitivity thresholds (left sidebar)
3. View real-time fraud detection results
4. Download report immediately
5. Click **Save This Analysis** to persist to history

### Tab 2: Analysis History
- List all past analyses with statistics
- Show the analyser for each analysis record
- **Re-download input file** - Access original data anytime
- **Re-download report** - Retrieve generated Excel/PDF
- **View results** - Expand to see full detection details
- Organized by user account (secure access)

### Admin Access
- A default admin account is seeded on first run
- The admin can create user accounts from the sidebar
- New users receive a one-time password and must change it on first login

## Test

```bash
pytest -q
```

## Architecture

**Database:**
- SQLite for user and analysis persistence
- SQLAlchemy ORM for data modeling
- Auto-created on first run at `fraud_detection.db`

**Authentication:**
- Admin-created accounts with email/password login
- First-login password reset for newly created users
- Bcrypt hashing for password security
- Streamlit session state for access control
- User ownership verification on all data access

**File Management:**
- Hybrid storage: files on disk, metadata in SQLite
- User-segregated directories for privacy
- Automatic file cleanup (optional)

## Project Documentation

- Full workflow and calculation guide: [PROJECT_WORKFLOW_AND_CALCULATIONS.md](PROJECT_WORKFLOW_AND_CALCULATIONS.md)
- Phase 1 implementation details: [IMPLEMENTATION_PHASE1.md](IMPLEMENTATION_PHASE1.md)

## Design Notes

- Configuration values are centralized in `src/config.py`
- Explainability is implemented in `src/explainability.py`
- The pipeline orchestration is implemented in `src/detection.py`
- Database models and auth logic in `src/database.py` and `src/auth.py`
- File storage management in `src/file_manager.py`
