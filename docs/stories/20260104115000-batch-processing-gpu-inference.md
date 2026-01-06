# Batch Processing and GPU Inference for ML Scoring Pipeline

## Summary
Added batch processing for ML scoring and optional GPU inference via cuML FIL, reducing processing time from days to potentially minutes for 7.7M records.

## Context / Problem
The ML scoring pipeline was extremely slow (50 blocks/s) due to:
1. Per-pair sequential processing instead of batch processing
2. CPU-only model inference
3. Non-vectorized embedding similarity calculations

With 7.7M records, the original approach would take several days to complete.

## What Changed

### 1. Batch Processing (`dedupe/ml/scoring_ml.py`)
- Added `score_batch()` method to MLScorer that processes all pairs in a block at once
- Batch feature extraction, model prediction, and calibration instead of per-pair
- Maintains same output format (MatchResult objects)

### 2. Pipeline Refactoring (`dedupe/pipeline.py`)
- Refactored `process_block()` to collect all pairs first, then batch process
- Uses `score_batch()` when MLScorer is available
- Backwards compatible with per-pair scoring

### 3. Vectorized Embedding Features (`dedupe/ml/features.py`)
- Added `_extract_embedding_features_batch()` for vectorized similarity calculations
- Batch lookup of embeddings using numpy operations
- Cosine, L2, dot product, and Manhattan distance computed in parallel

### 4. GPU Inference Support (`dedupe/ml/model.py`)
- Added `load_for_gpu_inference()` to load model into cuML FIL
- Added `predict_proba_gpu()` for GPU-accelerated batch prediction
- Added `is_gpu_available()` helper method

### 5. CLI Flag (`scripts/run_dedupe.py`)
- Added `--use-gpu` flag to enable GPU inference
- Reports GPU status at startup

## How to Test

### CPU Batch Processing (no dependencies needed)
```bash
python scripts/run_dedupe.py --query-file query.sql --out results_ml.csv --use-ml-scoring --embeddings-dir models/embeddings
```

### GPU Inference (requires cuML)
```bash
# Install cuML first
pip install cuml-cu12  # For CUDA 12.x
# or
conda install -c rapidsai cuml

# Run with GPU
python scripts/run_dedupe.py --query-file query.sql --out results_ml.csv --use-ml-scoring --embeddings-dir models/embeddings --use-gpu
```

### Benchmark on subset
```bash
python scripts/run_dedupe.py --query-file query.sql --out test.csv --use-ml-scoring --limit 100000
```

## Expected Performance

| Configuration | Est. Speed | 7.7M Records |
|--------------|------------|--------------|
| Original (per-pair) | 50 blocks/s | ~days |
| Batch processing (CPU) | 500+ blocks/s | ~hours |
| Batch + GPU (cuML FIL) | 5000+ blocks/s | ~minutes |

## Risk / Rollback Notes

### Low Risk
- Batch processing is backwards compatible - falls back to per-pair if `score_batch` not available
- GPU support is optional - gracefully falls back to CPU if cuML not installed or GPU fails

### Rollback
- Remove `use_gpu=True` parameter to disable GPU
- The old per-pair `score_pair()` method is still available as fallback

### Dependencies
- CPU batch: No new dependencies
- GPU: Requires `cuml` and `cupy` (optional)
