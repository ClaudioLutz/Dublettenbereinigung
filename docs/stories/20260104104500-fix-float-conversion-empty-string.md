# Fix float conversion error for empty strings in feature extraction

## Summary
Fixed `ValueError: could not convert string to float: ''` in address feature extraction by ensuring boolean evaluation before float conversion.

## Context / Problem
When running `train_ml_model.py`, the training pipeline failed during feature extraction with:
```
ValueError: could not convert string to float: ''
```

This occurred because Python's short-circuit `and` operator returns the last evaluated value, not necessarily a boolean. When `plz_a` or `plz_b` was an empty string, the expression `plz_a and plz_b and ...` would short-circuit and return `''`, which then failed when passed to `float('')`.

## What Changed
- `dedupe/ml/features.py`: Line 227-229 - wrapped operands in `bool()` for `plz_region_match` feature
- `dedupe/ml/features.py`: Line 257-259 - wrapped operands in `bool()` for `street_sig_match` feature

Before:
```python
features['plz_region_match'] = float(
    plz_a and plz_b and plz_a[:2] == plz_b[:2]
)
```

After:
```python
features['plz_region_match'] = float(
    bool(plz_a) and bool(plz_b) and plz_a[:2] == plz_b[:2]
)
```

## How to Test
```bash
python scripts/train_ml_model.py --results modular_results.csv --query query.sql --embeddings models/embeddings --output-dir models --version v1 --use-cv
```

The training should now proceed past the feature extraction step without the float conversion error.

## Risk / Rollback Notes
- Low risk: The logic is functionally equivalent but now handles empty strings correctly
- Rollback: Revert the `bool()` wrappers if any unexpected behavior occurs
