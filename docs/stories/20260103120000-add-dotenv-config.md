# Add .env Configuration for Database Credentials

## Summary

Added `.env` file support for database configuration, allowing scripts to automatically load SQL Server connection details without requiring command-line arguments or manual environment variable setup.

## Context / Problem

The ML pipeline scripts (`build_embeddings.py`, `train_ml_model.py`, `run_dedupe.py`) required database connection parameters to be passed via command-line arguments or manually set environment variables in PowerShell. This was cumbersome and error-prone, especially when running multiple scripts.

## What Changed

- **New files:**
  - `.env` - Contains actual database credentials (server: `PRODSVCREPORT70`, database: `CAG_Analyse`)
  - `.env.example` - Template file for documentation (already tracked in git)

- **Updated `requirements.txt`:**
  - Added `python-dotenv>=1.0.0` dependency

- **Updated scripts to auto-load `.env`:**
  - `scripts/build_embeddings.py`
  - `scripts/train_ml_model.py`
  - `scripts/run_dedupe.py`
  - `verify_ml_setup.py`

- **Updated `GETTING_STARTED_ML.md`:**
  - Added `.env` file as the recommended configuration method
  - Updated troubleshooting section with `.env` instructions

## How to Test

1. Install the new dependency:
   ```powershell
   pip install python-dotenv
   ```

2. Verify `.env` file exists with correct values:
   ```powershell
   cat .env
   ```

3. Run verification script (should detect database config automatically):
   ```powershell
   python verify_ml_setup.py
   ```

4. Run a script without `--db-server`/`--db-database` arguments:
   ```powershell
   python scripts/run_dedupe.py --query-file query.sql --out test.csv
   ```

## Risk / Rollback Notes

- **Low risk**: Scripts still accept command-line arguments which take precedence over `.env` values
- **Rollback**: Remove `load_dotenv()` calls from scripts and `python-dotenv` from requirements.txt
- **Security**: `.env` is already in `.gitignore` (line 51) so credentials won't be committed
