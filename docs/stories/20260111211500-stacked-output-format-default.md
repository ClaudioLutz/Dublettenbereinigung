# Stacked Output Format Default

## Summary

Modified `generate_tiered_output.py` to output stacked format (2 rows per pair with A/B positions) by default instead of wide format (1 row per pair with `_i`/`_j` suffixes). This makes the output easier for humans to review side-by-side.

## Context / Problem

The tiered output files (`auto_merge_pairs.csv`, `review_queue_pairs.csv`) were in wide format with columns like `vorname_i`, `vorname_j`, `name_i`, `name_j`, etc. This format is compact but hard to visually compare the two records in a pair.

Stacked format with position A/B rows makes it much easier for reviewers to compare records side-by-side in Excel or other tools.

## What Changed

- **scripts/generate_tiered_output.py**:
  - Added `wide_to_stacked()` function to convert wide format to stacked format
  - Added `--stacked` flag (default: True) for stacked output format
  - Added `--wide` flag to override and use wide format if needed
  - Updated `run_tier_assignment()` function to accept `stacked` parameter
  - Output filenames changed to `auto_merge_stacked.csv` and `review_queue_stacked.csv`

## How to Test

```bash
# Default: stacked format
python scripts/generate_tiered_output.py --input-dir _bmad-output/analysis/run_YYYYMMDD_HHMMSS

# Explicit wide format
python scripts/generate_tiered_output.py --input-dir _bmad-output/analysis/run_YYYYMMDD_HHMMSS --wide
```

Verify output:
- Stacked format: 2 rows per pair, `position` column with A/B values
- Wide format: 1 row per pair, columns with `_i`/`_j` suffixes

## Risk / Rollback Notes

- **Low risk**: This is an output format change only, no logic changes
- **Rollback**: Use `--wide` flag to get previous format
- **Downstream impact**: Any scripts consuming the tier output files need to handle stacked format (2 rows per pair instead of 1)
