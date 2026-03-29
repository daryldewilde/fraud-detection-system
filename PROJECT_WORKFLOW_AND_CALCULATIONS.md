# Fraud Detection System: How It Works

This document explains how the project works end-to-end, what calculations it performs, and how each calculation helps detect fraud.

## 1. System Purpose

The system analyzes transaction data and identifies suspicious behavior by combining:

- Rule checks
- Pattern checks
- Unusual behavior checks
- Weighted risk scoring
- Plain-language explanations

It is designed to support business users, compliance teams, and investigators.

## 2. End-to-End Workflow

The main execution flow is:

1. Load transaction file (CSV or XLSX)
2. Clean and validate data
3. Build hourly features per agent
4. Run fraud detection layers
5. Compute risk level
6. Generate human-readable reasons and details
7. Show results in UI and allow report export

## 3. Input Data and Cleaning

Expected columns:

- Agent
- Service
- Amount
- Status
- Paid At

Cleaning and normalization steps:

1. Column aliases are mapped to canonical names.
2. Service values are lowercased.
3. Status values are uppercased.
4. Amount is converted to numeric.
5. Paid At is converted to datetime.
6. Rows with missing required fields are removed.
7. Negative amounts are removed.
8. Rows are sorted by time.

How this helps fraud detection:

- Prevents false alerts caused by bad formatting.
- Makes feature calculations consistent.
- Ensures time-based behavior analysis is reliable.

## 4. Feature Engineering (Per Agent, Per Hour)

The core aggregation window is one hour per agent.

For each `(Agent, hour)` bucket, the system computes:

- `tx_count`: total number of transactions
- `success_count`: number of successful transactions
- `fail_count`: number of failed transactions
- `fail_ratio`: failed share of transactions
- `avg_amount`: average transaction amount
- `max_amount`: maximum transaction amount

### Formulas

Let $N$ be transactions in an agent-hour window.

- $\text{tx\_count} = N$
- $\text{success\_count} = \sum 1[\text{Status} = SUCCESS]$
- $\text{fail\_count} = \sum 1[\text{Status} \neq SUCCESS]$
- $\text{fail\_ratio} = \frac{\text{fail\_count}}{\text{tx\_count}}$
- $\text{avg\_amount} = \frac{1}{N}\sum \text{Amount}$
- $\text{max\_amount} = \max(\text{Amount})$

How this helps fraud detection:

- High `tx_count` can indicate rapid abuse or bot-like activity.
- High `fail_ratio` often signals probing, retries, or blocked fraudulent attempts.
- Extreme amount behavior can indicate attempted cash-out or laundering spikes.

## 5. Detection Layer A: Rule-Based Flags

The rule layer creates boolean flags from threshold checks.

Default thresholds from configuration:

- Velocity threshold: `50`
- Failure ratio threshold: `0.35`
- Service concentration threshold: `0.9`

### Rule Calculations

- `velocity_flag = (tx_count >= velocity_threshold)`
- `failure_flag = (fail_ratio >= failure_ratio_threshold)`
- `service_distribution_flag = (dominant_service_ratio >= service_concentration_threshold)`

How this helps fraud detection:

- Transparent and easy to audit.
- Fast baseline signal for known risk behavior.
- Good for compliance and operational rules.

## 6. Detection Layer B: Pattern Flags

The pattern layer detects suspicious sequence behavior.

### Pattern 1: Cashout then immediate movement

Flag condition (same agent):

1. A `cashout` transaction is followed quickly by `cashin` or `transfer`.
2. Time gap is within `pattern_window_minutes` (default: 10).
3. Amounts are close (ratio within 0.9 to 1.1).

Why this matters:

- Can indicate rapid value extraction and movement to obscure funds.

### Pattern 2: Repeated similar amount chain

Flag condition:

1. For same `(Agent, hour, Service, Amount)` bucket,
2. Repeat count reaches `repeated_chain_min_count` (default: 3).

Why this matters:

- Repeated near-identical transfers may signal scripted fraud, mule routing, or testing loops.

## 7. Detection Layer C: Unusual Behavior (Isolation Forest)

The anomaly layer uses Isolation Forest on numeric features:

- `tx_count`
- `success_count`
- `fail_count`
- `fail_ratio`
- `avg_amount`
- `max_amount`

Defaults:

- Contamination: `0.08`
- Minimum rows to run anomaly model: `12`

Output:

- `anomaly_flag` (True/False)
- `anomaly_score` (higher means more unusual)

How this helps fraud detection:

- Catches behavior that does not match known rule patterns.
- Useful for emerging fraud strategies.

## 8. Risk Level Calculation

The final risk level is a weighted sum of flags.

Default weights:

- Velocity: `0.30`
- Failure: `0.30`
- Anomaly: `0.40`
- Pattern: `0.20`
- Service concentration: `0.15`

### Formula

$$
	ext{risk\_level} =
(\text{velocity\_flag}\times0.30)
+ (\text{failure\_flag}\times0.30)
+ (\text{anomaly\_flag}\times0.40)
+ (\text{pattern\_flag}\times0.20)
+ (\text{service\_distribution\_flag}\times0.15)
$$

Then clipped to $[0,1]$.

Suspicious decision:

- `is_suspicious = (risk_level > risk_threshold)`
- Default `risk_threshold = 0.6`

How this helps fraud detection:

- Combines multiple weak/strong signals into a single triage score.
- Supports priority ranking of cases for investigation.

## 9. Explainability Output

Each result row includes:

- `reasons`: plain-language reason text for triggered signals
- `details`: numeric summary (`tx_count`, `fail_ratio`, `avg_amount`, `max_amount`)

How this helps fraud detection:

- Investigators can understand why a case was flagged.
- Supports audit reviews and regulator-facing evidence.

## 10. Report Fields for Audit

Exported report includes:

- Agent
- Time
- Risk level
- Reason
- Key details

How this helps fraud detection:

- Creates traceable, reviewable outputs for operations and compliance.

## 11. Why Multi-Layer Detection Is Stronger

Using only one method can miss cases:

- Rules alone miss novel fraud behavior.
- Anomaly alone can be noisy.
- Patterns alone miss broad statistical changes.

Combining all layers improves:

- Coverage
- Explainability
- Practical investigation value

## 12. Practical Interpretation Guide

Use risk level as a triage signal:

- `0.00 - 0.39`: Low concern
- `0.40 - 0.59`: Medium concern, review context
- `0.60 - 1.00`: High concern, prioritize investigation

Suggested next actions for high-risk rows:

1. Review full transaction timeline for that agent.
2. Check linked accounts or destinations.
3. Confirm whether activity matches expected business behavior.
4. Escalate confirmed suspicious cases to compliance workflow.

---

If you tune thresholds or weights, document the changes and rationale to keep auditability strong.
