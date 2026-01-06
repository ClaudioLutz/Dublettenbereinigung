# Add GPU Inference via WSL2 with cuML

## Summary

Added GPU-accelerated ML inference for deduplication using cuML Forest Inference Library (FIL) running in WSL2, along with a hybrid workflow to handle SQL Server authentication limitations.

## Context / Problem

- ML scoring pipeline was extremely slow (~50 blocks/s for 7.7M records = days of processing)
- LightGBM's native GPU support only works for training, not inference
- cuML provides 50-150x speedup for tree model inference but is Linux-only
- WSL2 cannot use Windows Kerberos authentication for SQL Server

## What Changed

### GPU Inference Backend (`dedupe/ml/model.py`)
- Added `load_for_gpu_inference()` method with dual backend support:
  - cuML FIL (Linux/WSL): Primary, fastest option
  - ONNX Runtime GPU (Windows): Fallback option
- Added `predict_proba_gpu()` for GPU-accelerated batch prediction
- Added `_try_cuml_gpu()` and `_try_onnx_gpu()` helper methods

### Batch Scoring (`dedupe/ml/scoring_ml.py`)
- Added `score_batch()` method for batch ML inference
- Added `use_gpu` parameter to constructor
- GPU initialization on startup when `use_gpu=True`

### Batch Feature Extraction (`dedupe/ml/features.py`)
- Added `_extract_embedding_features_batch()` for vectorized similarity calculations
- Uses numpy broadcasting for efficient batch operations

### Pipeline Updates (`dedupe/pipeline.py`)
- Refactored `process_block()` to collect pairs first, then batch score
- Added `input_df` parameter to `run_pipeline()` for file-based input
- Handles both SQL and file input sources

### CLI Updates (`scripts/run_dedupe.py`)
- Added `--input-file` option to read from parquet/CSV
- Added `--export-only` flag to export SQL data to parquet
- Added `--use-gpu` flag for GPU inference

### WSL Setup (`scripts/setup_wsl_rapids.sh`, `run_wsl_gpu.ps1`)
- Created WSL2 RAPIDS environment setup script
- Updated launcher script for two-step workflow:
  1. Export SQL to parquet (Windows - has SQL auth)
  2. Process with GPU in WSL (Linux - has cuML)

### Dependencies (`requirements.txt`)
- Added optional GPU dependencies documentation

## How to Test

```powershell
# Full workflow (recommended)
.\run_wsl_gpu.ps1

# Or step by step:
# Step 1: Export data (Windows)
venv\Scripts\python scripts\run_dedupe.py --query-file query.sql --out results.csv --export-only

# Step 2: GPU processing (WSL)
wsl -d Ubuntu-22.04 -- bash -c "source ~/miniforge3/etc/profile.d/conda.sh && conda activate rapids-dedupe && cd /mnt/c/Lokal_Code/dubletten && python scripts/run_dedupe.py --input-file results.parquet --out results.csv --use-ml-scoring --use-gpu"
```

## Risk / Rollback Notes

- **Risk**: cuML accuracy may differ slightly from native LightGBM (Treelite float64 warning)
- **Risk**: Memory usage is high (~15GB for 7.7M records + embeddings)
- **Rollback**: Remove `--use-gpu` flag to use CPU inference
- **Rollback**: Use `--input-file` without `--use-gpu` for file-based CPU processing
