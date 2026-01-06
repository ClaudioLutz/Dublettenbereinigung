# Improve ML Entity Matching Quality

## Summary

Major improvements to the ML-based entity matching system to fix fundamental issues that caused the model to match different people at the same address instead of finding true duplicates. Implements three phases: name similarity gate, name-only embeddings, and diverse training data.

## Context / Problem

After analyzing the ML deduplication results, we identified critical issues:

1. **Model was essentially random** (AUC = 0.53, best_iteration=1)
   - The LightGBM model learned almost nothing
   - Max confidence was only 61.9%
   - "Matches" were different people at the same address (e.g., "Denise Kratlinger" vs "René Déglise")

2. **Root causes identified:**
   - **Address-contaminated embeddings**: Text template included address, so people at same address had high similarity regardless of name
   - **Flawed training data**: Both positives and negatives came from same-address blocking, making them indistinguishable
   - **No name similarity enforcement**: No minimum threshold prevented matching people with completely different names

## What Changed

### Phase 1: Name Similarity Hard Gate
**Files modified:** `dedupe/ml/scoring_ml.py`

- Added `min_name_similarity` parameter (default: 0.50) to `MLScorer`
- Pairs with name similarity below threshold are rejected before ML scoring
- Tracks `name_similarity_rejections` in statistics
- Prevents same-address different-person matches from being reported

### Phase 2: Name-Only Embeddings
**Files modified:**
- `dedupe/ml/config.py` - Added `TEXT_TEMPLATE_NAME_ONLY`, `NAME_ONLY_VERSION_SUFFIX`, `DEFAULT_EMBEDDING_MODE`
- `dedupe/ml/embeddings.py` - Added `name_only` parameter to `prepare_text()` and `prepare_texts()`, updated `save()/load()` with version suffix, added `load_name_only()` method
- `dedupe/ml/features.py` - Added 4 new features: `name_emb_cosine_similarity`, `name_emb_l2_distance`, `name_emb_dot_product`, `name_emb_manhattan_distance`
- `scripts/build_embeddings.py` - Added `--name-only` flag

Name-only embeddings use template `"[NAME] {first} {last} {name2}"` without address fields, preventing address contamination.

### Phase 3: Diverse Training Data
**Files modified:** `dedupe/ml_training/silver_labels.py`

- Added `generate_diverse_negatives()` method with balanced mix:
  - 40% easy negatives: random pairs (different address, different name)
  - 30% medium negatives: same last name OR same PLZ
  - 30% hard negatives: same address block, different names
- Changed default `hard_negative_strategy` from `'blocking'` to `'diverse'`
- This diversity is critical for teaching the model the difference between true duplicates and same-address-different-person

## How to Test

### 1. Generate name-only embeddings:
```bash
python scripts/build_embeddings.py \
    --query-file query.sql \
    --output-dir models/embeddings \
    --name-only \
    --device cuda
```

### 2. Retrain the model with diverse training data:
```bash
python scripts/train_ml_model.py \
    --results modular_results.csv \
    --query query.sql \
    --embeddings models/embeddings \
    --output-dir models \
    --use-cv
```

### 3. Run deduplication with improved settings:
```bash
python scripts/run_dedupe.py \
    --query-file query.sql \
    --out results_ml_improved.csv \
    --use-ml-scoring \
    --ml-model-dir models \
    --embeddings-dir models/embeddings
```

### 4. Verify results:
- Model AUC should be significantly higher than 0.53
- High-confidence matches should show similar names (not just same address)
- Name similarity gate statistics should show rejections

## Risk / Rollback Notes

### Risks:
- **Name similarity threshold** may filter out legitimate matches with heavily misspelled names
  - Mitigation: Threshold is configurable via `min_name_similarity` parameter
  - Can set to 0.0 to disable the gate

- **Name-only embeddings** require regenerating embeddings (~1 hour for 7.7M records)
  - Mitigation: Can run alongside existing full embeddings
  - Old embeddings remain in place (different filename)

- **Diverse training data** changes the model's behavior
  - Mitigation: Backup existing model before retraining
  - Can revert to `hard_negative_strategy='blocking'` if needed

### Rollback:
1. To disable name similarity gate: Set `min_name_similarity=0.0` when loading MLScorer
2. To use old embeddings: Don't pass name_embedding_store to FeatureExtractor
3. To use old training strategy: Set `hard_negative_strategy='mixed'` in SilverLabelGenerator

### Files changed:
- `dedupe/ml/scoring_ml.py`
- `dedupe/ml/config.py`
- `dedupe/ml/embeddings.py`
- `dedupe/ml/features.py`
- `dedupe/ml_training/silver_labels.py`
- `scripts/build_embeddings.py`
