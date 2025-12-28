# Swisstopo Normalization Observability and Consistency

## Summary
Improved address normalization observability by adding normalization evidence to `results.csv` and creating a new `normalization_audit.csv` log. Also ensured consistent usage of 4-digit PLZ for address blocking keys.

## Context / Problem
- Normalization results were not visible in the final `results.csv`, making it hard to verify if swisstopo matching was working.
- Address blocking keys were using raw PLZ (potentially 6 digits) while matching swisstopo used 4 digits, leading to inconsistencies.
- A way to audit all normalization changes (not just for duplicate pairs) was requested.

## What Changed
- **dedupe/preprocess.py**:
  - Implemented consistent 4-digit PLZ extraction for blocking keys (`addr_key_building`, `addr_key_typo`).
  - Captured swisstopo join outputs (`match_type`, `adr_egaid`, references) and exposed them in the output.
  - Added a `swis_changed` flag to track if normalization altered the address.
- **dedupe/pipeline.py**:
  - Updated `_write_results` to include normalization fields in `results.csv`.
  - Added `_write_audit_log` to write `normalization_audit.csv` for matched/changed records.
  - Added per-chunk normalization stats printing to console.
- **scripts/run_dedupe.py**:
  - Added `--norm-audit-out` argument to enable the audit log.
- **tests/test_swisstopo_normalization.py**:
  - Added integration tests for PLZ4 key consistency and full swisstopo normalization flow using a temporary DuckDB.

## How to Test
1. Run the new integration tests:
   ```bash
   python -m pytest tests/test_swisstopo_normalization.py -v
   ```
2. Run the pipeline with swisstopo DB and audit log enabled (requires `swisstopo.duckdb`):
   ```bash
   python scripts/run_dedupe.py \
     --query-file queries/example.sql \
     --out results.csv \
     --swisstopo-db swisstopo.duckdb \
     --norm-audit-out audit.csv
   ```
   - Verify `results.csv` contains columns like `swis_match_type`, `plz4_used`, etc.
   - Verify `audit.csv` is created and contains changed addresses.
   - Verify console output shows "Normalization matched X ... Y changed keys".

## Risk / Rollback Notes
- **Risk**: Increased memory usage due to storing normalization metadata for each chunk.
- **Rollback**: Revert changes to `dedupe/preprocess.py` and `dedupe/pipeline.py` to restore previous behavior.
