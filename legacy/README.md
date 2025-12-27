# Legacy Code

This directory contains legacy code that has been quarantined and is no longer supported.

The active pipeline is located in `dedupe/` and can be run via `scripts/run_dedupe.py`.

## Files
- `duplicate_checker_optimized.py`: Old monolithic duplicate checker.
- `run_optimized_analysis.py`: Legacy runner script.
- `data.py`: Legacy data loading helper with hardcoded credentials/queries.
- `check_edges.py`, `generate_duplicate_report.py`, `show_duplicates.py`: Legacy utility scripts.
