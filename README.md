# RateAtlas · BracketForge (`rateatlas-ingest`)

> Signal-based IRS ingestion microservice that detects page changes, scrapes, normalizes, and archives tax brackets for the RateAtlas platform.
>
> Part of the [RateAtlas](../README.md) stack.

## Overview

`tax_bracket_ingest` is a standalone Python microservice deployed as an AWS Lambda container. It runs on a weekly schedule and automatically:

1. **Probes** the IRS tax bracket page for the "Page Last Reviewed or Updated" date.
2. **Compares** that date against the last seen date stored in Postgres.
3. **Exits early** if the page has not changed since the last ingest — no unnecessary processing.
4. **Fetches and parses** filing-status–specific brackets into pandas DataFrames if the page has changed.
5. **Normalizes** and cleans the data into a consistent CSV format.
6. **Archives** the updated CSV in an AWS S3 bucket for backup.
7. **Pushes** the new records to the downstream Spring Boot API via `POST /api/v1/tax/upload`.
8. **Updates** the `ingest_metadata` table in Postgres with the new page date and ingest timestamp.

This ensures the backend always has the latest brackets, S3 retains an immutable historical record, and unnecessary ingest runs are avoided when the IRS page hasn't changed.

---

## Table of Contents

- [RateAtlas · BracketForge (`rateatlas-ingest`)](#rateatlas--bracketforge-rateatlas-ingest)
  - [Overview](#overview)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Implementation Status](#implementation-status)
  - [Project Structure](#project-structure)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Scheduling](#scheduling)
  - [Usage](#usage)
  - [Testing](#testing)
  - [Continuous Integration](#continuous-integration)
  - [Contributing](#contributing)
  - [License](#license)

---

## Features

- **Signal-based change detection** — probes the IRS page date before scraping, skipping unnecessary runs.
- **Postgres metadata tracking** — persists `last_seen_page_update`, `last_ingested_at`, `ingest_run_count`, and `ingest_skip_count` to the `ingest_metadata` table.
- **Automated scraping** of IRS tax bracket HTML when a page change is detected.
- **Data parsing** for all four filing statuses (Single, Married Filing Jointly, Married Filing Separately, Head of Household).
- **Normalization** to a standard CSV schema, ready for analytics or database ingestion.
- **S3 archival** to maintain a complete historical record (`history.csv` in S3).
- **Spring API integration** — HTTP POST of new bracket rows to the TaxIQ backend.
- **Extensible design** to support additional storage backends or notification steps.
- **Comprehensive pytest suite** (unit and integration markers) with 90%+ coverage enforcement.
- **GitHub Actions CI/CD** with coverage enforcement and automated Lambda deployments via OIDC.

---

## Implementation Status

| Component                          | Status                    |
|------------------------------------|---------------------------|
| Signal-based page change detection | ✅ Implemented            |
| Postgres metadata tracking         | ✅ Implemented            |
| Fetch IRS HTML                     | ✅ Implemented            |
| Parse filing-status tables         | ✅ Implemented            |
| Normalize to CSV schema            | ✅ Implemented            |
| Archive to S3                      | ✅ Implemented            |
| Push to Spring backend             | ✅ Implemented            |
| AWS Lambda deployment              | ✅ Implemented            |
| Weekly EventBridge schedule        | ⚙️ Manual setup required  |
| Alternative storage backends       | 🔲 Planned                |
| Notification hooks                 | 🔲 Planned                |

> ✅ = Complete & tested  ⚙️ = Configured but requires external setup  🔲 = Not yet implemented

---

## Project Structure

```txt
tax_bracket_ingest/
├── scraper/
│   ├── fetch.py        # Full IRS page fetch with retries and timeout
│   └── probe.py        # Lightweight page date extraction (change detection gate)
├── parser/
│   ├── parser.py       # HTML table parsing into structured dicts
│   └── normalize.py    # DataFrame normalization and schema standardization
├── db/
│   └── metadata.py     # Postgres read/write for ingest_metadata table
├── run_ingest.py       # Orchestration — gate logic, pipeline, metadata updates
└── logging_config.py   # Structured logging setup

tests/
├── unit/
│   ├── test_scraper.py
│   ├── test_probe.py
│   ├── test_parser.py
│   ├── test_normalize.py
│   ├── test_metadata.py
│   └── test_push_backend.py
└── integration/
    └── test_run_ingest.py
```

---

## Installation

1. Clone this repository:

```bash
   git clone https://github.com/CHA0sTIG3R/rateatlas-ingest.git
   cd rateatlas-ingest
```

1. Create a virtual environment and activate it:

```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   .venv\Scripts\activate     # Windows
```

1. Install dependencies:

```bash
   pip install -r requirements.txt        # runtime dependencies
   pip install -r requirements-dev.txt    # development & testing extras
```

---

## Configuration

Create a `.env` file in the project root with the following values:

```ini
# AWS
AWS_REGION=us-east-1
S3_BUCKET=your-s3-bucket-name
S3_KEY=history.csv
DRY_RUN=1               # set to 0 to enable writes to S3/backend

# Backend
BACKEND_URL=https://your-backend
INGEST_API_KEY=your-shared-secret
ENABLE_BACKEND_PUSH=0   # set to 1 to enable backend uploads

# Database (required for change detection and metadata tracking)
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require

# Logging
ENV=dev
LOG_TO_FILE=1
LOG_PATH=logs/tax_bracket_ingest.log
LOG_RETENTION_DAYS=7

# AWS credentials (only when not using instance roles/OIDC)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=...   # optional
```

> Keep production secrets in AWS SSM Parameter Store or GitHub Actions secrets. Never commit `.env` files.

---

## Scheduling

The microservice is deployed as an AWS Lambda and triggered Weekly via AWS EventBridge. Weekly polling is used instead of a fixed annual schedule because the IRS page update date varies year to year — in 2025 for example, the page updated February 20, 2026 instead of the previously assumed November date.

The change detection gate ensures that weekly runs are cheap — if the IRS page hasn't updated, the Lambda exits early after a lightweight probe with no scraping, no S3 writes, and no backend push.

**EventBridge schedule recommendation:** every Friday at 12:00 UTC:

```sh
cron(0 12 ? * FRI *)
```

For local cron-based runs:

```cron
0 12 ? * FRI * cd /path/to/rateatlas-ingest && /path/to/.venv/bin/python -m tax_bracket_ingest.run_ingest >> ingest.log 2>&1
```

---

## Usage

Run the end-to-end ingestion manually:

```bash
python -m tax_bracket_ingest.run_ingest
```

`DRY_RUN` defaults to `1` — logs actions without touching S3, the backend, or the database. Set `DRY_RUN=0` and `ENABLE_BACKEND_PUSH=1` for a real run.

**Expected output when page has not changed:**

```txt
page_not_updated — IRS page has not been updated since last ingest, skipping processing
ingest_finished — Ingest process finished
```

**Expected output when page has changed:**

```txt
page_updated — IRS page has been updated since last ingest, proceeding with processing
append_new_data — Appending new data to historical CSV
pushed_to_backend — Pushed current tax data to backend
updated_s3 — Updated historical CSV in S3
ingest_complete — Ingest process completed successfully
```

---

## Testing

Run the full test suite:

```bash
pytest
```

- **Unit tests only:** `pytest -m "not integration"`
- **Integration tests only:** `pytest -m integration`

Coverage reports are generated automatically (`coverage.xml`). CI enforces 90%+ coverage.

---

## Continuous Integration

GitHub Actions (`.github/workflows/cicd.yml`) handles:

- Running pytest with coverage on Python 3.11
- Uploading coverage reports to Codecov
- Assuming an AWS role via OIDC
- Building the Lambda container image and pushing to ECR
- Updating the live Lambda function to the latest image
- Injecting all environment variables from GitHub Actions secrets and SSM

CI runs on every push. Deployment runs only on pushes to `main`.

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/name`
3. Commit changes: `git commit -m "Add feature"`
4. Push and open a PR targeting `main`

Ensure tests pass and coverage remains above 90%.

---

## License

Currently unlicensed — a permissive license will be added in the near future.
