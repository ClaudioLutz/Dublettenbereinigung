# Fix ML training pipeline issues on Windows

## Summary

Fixed issues preventing ML training pipeline Phase 3 from running:
1. Missing `embeddings_v1_meta.npz` file due to Windows memmap file locking
2. CSV parsing failure in `silver_labels.py` due to non-UTF8 encoding
3. Missing return keys in `compare_names_with_swap()` for ML feature extraction
4. Incorrect arguments in `get_first_word_bonus()` call in features.py
5. Boolean-to-float conversion error for cologne phonetics matching

## Context / Problem

When running `train_ml_model.py` on Windows, five errors occurred sequentially:
1. `FileNotFoundError: Metadata file not found: models\embeddings\embeddings_v1_meta.npz`
2. `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc4` when parsing `modular_results.csv`
3. `KeyError: 'normal_first'` during ML feature extraction
4. `TypeError: get_first_word_bonus() missing 2 required positional arguments`
5. `ValueError: could not convert string to float: ''` in cologne phonetics

Root causes:
- **Metadata issue**: On Windows, memory-mapped files are locked by the process. The `encode_large_dataset()` method did not explicitly close memmap references before `store.save()`, causing file lock conflicts.
- **Encoding issue**: CSV files with German/French names use Latin-1/CP1252 encoding, not UTF-8.
- **Feature extraction issue**: `compare_names_with_swap()` did not return individual similarity scores (`normal_first`, `normal_last`, etc.) that the ML feature extractor expects.
- **Function call issue**: `get_first_word_bonus()` was called with wrong argument order and missing `house`/`ort` parameters.
- **Type conversion issue**: Boolean expression short-circuits to empty string `''`, and `float('')` fails.

## What Changed

- **dedupe/ml/embeddings.py**:
  - `encode_large_dataset()`: Added `del embeddings` after encoding to release Windows file lock
  - `save()`: Added explicit memmap cleanup when `skip_embeddings=True` to release file lock before saving metadata

- **dedupe/ml_training/silver_labels.py**:
  - Added `_read_csv_with_encoding()` helper method with multi-encoding support (UTF-8, Latin-1, CP1252)
  - Updated all CSV reads to use the helper: `extract_positives_from_results()`, `generate_hard_negatives_from_blocking()`, and `generate_negatives_from_low_confidence()`

- **scripts/rebuild_embeddings_metadata.py** (new):
  - Utility script to regenerate missing metadata file from database

- **dedupe/scoring.py**:
  - Extended `compare_names_with_swap()` return dict to include individual scores: `normal_first`, `normal_last`, `swapped_first`, `swapped_last` (required by ML feature extraction)

- **dedupe/ml/features.py**:
  - Fixed `_extract_interaction_features()` call to `get_first_word_bonus()` with correct argument order and added missing `house` and `ort` parameters
  - Fixed cologne phonetics boolean-to-float conversion that failed on empty strings

## How to Test

```powershell
# 1. Verify metadata file exists
dir models\embeddings\embeddings_v1_meta.npz

# 2. Test CSV parsing with encoding
python -c "import pandas as pd; df = pd.read_csv('modular_results.csv', sep=';', encoding='latin-1'); print(f'Loaded {len(df)} rows')"

# 3. Run Phase 3 training
python scripts/train_ml_model.py --results modular_results.csv --query query.sql --embeddings models/embeddings --output-dir models --version v1 --use-cv
```

## Risk / Rollback Notes

- **Low risk**: Changes only affect file cleanup, encoding handling, and return value extension
- **Rollback**: Revert changes to `embeddings.py`, `silver_labels.py`, and `scoring.py`
- **Note**: If metadata file is lost again, run `python scripts/rebuild_embeddings_metadata.py` to regenerate
- **Backward compatible**: The `scoring.py` change adds new keys without removing existing ones
