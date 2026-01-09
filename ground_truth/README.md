# Ground Truth Directory

This directory contains manually validated entity pairs for regression testing and pattern discovery.

## File Structure

- `calibration_set.csv` - 30 manually labeled pairs for LLM calibration (Phase 2)
- `clear_duplicates.csv` - High-confidence matches (70-90 pairs, score ≥95%)
- `clear_non_duplicates.csv` - High-confidence non-matches (70-90 pairs, score <75%)
- `edge_cases.csv` - Borderline cases (45-65 pairs, score 65-95%)
- `boundary_cases.csv` - At-threshold cases (20-25 pairs, near 75% threshold)

## CSV Format

Each file contains the same columns as `modular_results.csv` plus:
- `manual_label` - Human annotation (DUPLICATE/NOT_DUPLICATE)
- `labeled_by` - Name or ID of labeler
- `labeled_date` - Date of labeling (YYYY-MM-DD)
- `notes` - Optional notes about the pair

## Usage

These files are used by:
1. Regression tests (`tests/test_business_rules.py`) to prevent unintended rule changes
2. Pattern discovery analysis to validate LLM predictions
3. Continuous improvement feedback loop for rule refinement

## Versioning

Every update to ground truth files creates a backup in `ground_truth_archive/YYYYMMDD_HHMMSS/`.
See git history for change tracking and rollback.
