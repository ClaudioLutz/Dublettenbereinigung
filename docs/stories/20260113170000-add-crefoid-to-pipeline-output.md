# Add CrefoID to Pipeline Output

## Summary

Added CrefoID (unique record identifier) to the pipeline output and changed match_id to use CrefoIDs instead of internal indices. Also added single-command pipeline orchestration script.

## Context / Problem

The stacked output format was missing the CrefoID column, making it impossible to trace pairs back to source records. The match_id was using internal indices (e.g., `123_456`) which change between runs, making it hard to identify the same pair across different pipeline executions.

## What Changed

- **dedupe/analysis/format_converter.py**
  - Added `crefo_i` and `crefo_j` columns to the pairs format conversion

- **scripts/generate_tiered_output.py**
  - Changed match_id to use CrefoIDs: `CrefoID1_CrefoID2` instead of `i_j`
  - Added `crefo` to priority columns in stacked output
  - Column order: match_id, position, crefo, cluster, confidence, reason, vorname, name, strasse, ...

- **scripts/run_full_pipeline.py** (new file)
  - Single command to run all pipeline stages
  - Usage: `python scripts/run_full_pipeline.py --query-file query.sql`

## How to Test

```bash
# Re-run clustering to pick up crefo columns
python -m dedupe.analysis.pattern_discovery --input modular_results_fresh.csv --phase 1 --clusters 15 --skip-validation

# Run tier assignment
python scripts/generate_tiered_output.py

# Verify output has crefo column and CrefoID-based match_id
head -3 _bmad-output/analysis/run_*/auto_merge_stacked.csv
```

Expected output format:
```
match_id               position  crefo       cluster  vorname  name
400005263_428210989    A         400005263   13       Juliette Jost
400005263_428210989    B         428210989   13       Jost     Juliette
```

## Risk / Rollback Notes

- Low risk: Format change only, no logic changes
- Backward compatible: Falls back to index-based match_id if crefo columns missing
- Rollback: Revert the commit and re-run pipeline
