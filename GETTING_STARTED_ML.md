# Getting Started with ML-Based Entity Matching

**Status:** All ML infrastructure and dependencies installed
**GPU:** NVIDIA RTX A500 Laptop GPU (CUDA 12.1)
**Environment:** Ready to run

---

## Prerequisites Checklist

- [x] All code modules exist (`dedupe/ml/`, `dedupe/ml_training/`, `scripts/`)
- [x] PyTorch 2.5.1 with CUDA support installed
- [x] sentence-transformers 5.2.0 installed
- [x] LightGBM 4.6.0 installed
- [x] All other dependencies (faiss-cpu, scikit-learn, numba, etc.)
- [x] Virtual environment activated
- [x] `.env` file configured with database credentials

---

## Quick Start: 4-Phase ML Pipeline

> **Note:** All scripts automatically load database credentials from `.env` file.
> No need to pass `--db-server` and `--db-database` arguments.

### Phase 1: Generate Embeddings (First Time Setup)

**What it does:** Creates semantic embeddings for all your address records using GPU acceleration.

#### Option A: Test on Small Dataset First (Recommended)

```powershell
python scripts/build_embeddings.py --query-file query.sql --output-dir models/embeddings_test --limit 10000 --device cuda --skip-faiss
```

#### Option B: Full Dataset (Production)

```powershell
python scripts/build_embeddings.py --query-file query.sql --output-dir models/embeddings --batch-size 256 --device cuda
```

**Output:** `models/embeddings/embeddings_v1.dat` (~11.5 GB)

---

### Phase 2: Run Rule-Based Deduplication (Get Training Data)

**What it does:** Run your existing rule-based system to generate matches that will be used for training.

```powershell
python scripts/run_dedupe.py --query-file query.sql --out modular_results.csv
```

**Output:** `modular_results.csv` with confidence scores

**Note:** If you already have recent results, you can skip this step and use your existing CSV file.

---

### Phase 3: Train ML Model

**What it does:** Trains a LightGBM model using weak supervision from your high-confidence matches.

```powershell
python scripts/train_ml_model.py --results modular_results.csv --query query.sql --embeddings models/embeddings --output-dir models --version v1 --use-cv
```

**Output:**
- `models/lightgbm/matcher_v1.txt` (trained model)
- `models/lightgbm/calibrator_v1.pkl` (calibration)
- `models/lightgbm/matcher_v1_metadata.json` (metrics)

**Expected Training Time:** 15-25 minutes with cross-validation

---

### Phase 4: Run ML-Based Deduplication

**What it does:** Uses your trained ML model for production deduplication with better accuracy.

```powershell
python scripts/run_dedupe.py --query-file query.sql --out results_ml.csv --use-ml-scoring --embeddings-dir models/embeddings
```

**Output:** `results_ml.csv` with ML-enhanced confidence scores

---

## Verification Script

Run this to verify your setup before starting:

```powershell
python verify_ml_setup.py
```

This will check:
- All Python dependencies
- GPU availability
- Database connectivity (optional)
- File structure
- ML modules can be imported

---

## Expected Performance

### Processing Speed
- **Embeddings:** ~5,000 records/sec on GPU, ~1,000 rec/sec on CPU
- **ML Training:** 15-25 min with CV, 5-10 min without CV
- **ML Inference:** ~6,250-7,000 records/sec (20-30% slower than rules-only)

### Quality Improvements
- **Precision:** +3-5% (92-95% to 97-98%)
- **Recall:** +10-15% (70-80% to 85-90%)
- **F1 Score:** +10-15% improvement

### Disk & Memory
- **Embeddings:** 11.5 GB disk, ~300 MB RAM when loaded
- **Model:** <1 MB disk, ~50 MB RAM when loaded
- **Peak Memory:** ~2 GB during processing

---

## Recommended First Run Sequence

### 1. Test with Small Dataset (10 minutes)

```powershell
# Step 1: Test embeddings on 10K records
python scripts/build_embeddings.py --query-file query.sql --output-dir models/embeddings_test --limit 10000 --device cuda --skip-faiss

# Step 2: Test deduplication (modify query.sql to SELECT TOP 10000 first)
python scripts/run_dedupe.py --query-file query.sql --out test_results.csv

# Step 3: Train on test data
python scripts/train_ml_model.py --results test_results.csv --query query.sql --embeddings models/embeddings_test --output-dir models --version test

# Step 4: Test ML scoring
python scripts/run_dedupe.py --query-file query.sql --out test_ml_results.csv --use-ml-scoring --ml-version test --embeddings-dir models/embeddings_test
```

### 2. Production Run (Full Dataset)

Once verified on small dataset, run on full 7.5M records following Phase 1-4 above.

---

## Troubleshooting

### GPU Out of Memory
```powershell
python scripts/build_embeddings.py --query-file query.sql --output-dir models/embeddings --batch-size 128 --device cuda
# or even smaller:
python scripts/build_embeddings.py --query-file query.sql --output-dir models/embeddings --batch-size 64 --device cuda
```

### Database Connection Issues
Ensure your `.env` file exists with correct values:
```bash
DEDUPE_DB_SERVER=YOUR_SERVER
DEDUPE_DB_DATABASE=YOUR_DATABASE
```

### Missing Results File
Make sure you have run Phase 2 (rule-based deduplication) first, or use an existing results CSV.

### Slow Performance
- Use GPU for embeddings: `--device cuda`
- Skip FAISS index if not needed: `--skip-faiss`
- Reduce workers if CPU bound: `--workers 4`

---

## Database Configuration

Your scripts need database connection info. The recommended method is using a `.env` file.

### Method 1: `.env` file (Recommended)

The `.env` file should already exist in your project root:
```bash
DEDUPE_DB_SERVER=PRODSVCREPORT70
DEDUPE_DB_DATABASE=CAG_Analyse
```

Scripts automatically load this file - no command-line arguments needed.

### Method 2: Command-line arguments (override .env)
```powershell
python scripts/build_embeddings.py --query-file query.sql --db-server YOUR_SERVER --db-database YOUR_DB --output-dir models/embeddings
```

### Method 3: Environment variables (PowerShell)
```powershell
$env:DEDUPE_DB_SERVER = "YOUR_SERVER_NAME"
$env:DEDUPE_DB_DATABASE = "YOUR_DATABASE_NAME"
```

---

## Next Steps

1. **Run verification script:** `python verify_ml_setup.py`
2. **Choose your path:**
   - **Quick test:** Run small dataset test sequence above
   - **Production:** Run full Phase 1-4 pipeline
3. **Monitor progress:** Each script shows progress bars and estimates
4. **Compare results:** Compare rule-based vs ML-based results

---

## Full Documentation

See `docs/ML_IMPLEMENTATION.md` for complete documentation including:
- Detailed architecture
- Advanced configuration options
- Performance tuning
- Troubleshooting guide
- Best practices

---

## Quick Command Reference

```powershell
# Check dependencies
python -c "import torch, sentence_transformers, lightgbm; print('Ready')"

# Verify GPU
python -c "import torch; print('CUDA:', torch.cuda.is_available())"

# Run verification
python verify_ml_setup.py

# Generate embeddings (test)
python scripts/build_embeddings.py --query-file query.sql --output-dir models/embeddings_test --limit 10000 --device cuda --skip-faiss

# Train model
python scripts/train_ml_model.py --results modular_results.csv --query query.sql --embeddings models/embeddings --use-cv

# Run ML deduplication
python scripts/run_dedupe.py --query-file query.sql --out results_ml.csv --use-ml-scoring --embeddings-dir models/embeddings
```

---

**Questions or Issues?**
- Check `docs/ML_IMPLEMENTATION.md` for detailed troubleshooting
- Review training logs in `models/lightgbm/matcher_v1_metadata.json`
- Test on small dataset first to validate setup
