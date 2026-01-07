# Dubletten Documentation Index

> **Swiss Entity Deduplication Pipeline**
>
> Last Updated: 2026-01-06 | Project Type: Data Pipeline + ML

---

## Quick Navigation

| Document | Description |
|----------|-------------|
| [Architecture](architecture.md) | System architecture, components, data flow |
| [Getting Started (ML)](../GETTING_STARTED_ML.md) | Quick start guide for ML pipeline |
| [System Architecture](SYSTEM_ARCHITECTURE.md) | Detailed system design |
| [Business Rules](businessrules.md) | Entity matching rules and thresholds |
| [Address Blocking](address_based_blocking.md) | Blocking strategy documentation |

---

## Project Overview

**Dubletten** is a production-grade entity deduplication system designed for Swiss address databases containing 7.5M+ records. It combines traditional fuzzy matching with ML-enhanced scoring.

### Key Capabilities

- **Scale:** Processes 7.5M records in ~30 minutes
- **Precision:** 97-98% (ML mode)
- **Recall:** 85-90% (ML mode)
- **GPU Support:** CUDA acceleration for embeddings and inference

### Architecture Pattern

```
Data Source -> Preprocessing -> Blocking -> Candidate Gen -> Scoring -> Output
                                                             |
                                            [Rule-based OR ML-based]
```

---

## Entry Points

### Production Scripts

| Script | Purpose |
|--------|---------|
| `scripts/run_dedupe.py` | Main deduplication pipeline |
| `scripts/build_embeddings.py` | Generate sentence embeddings |
| `scripts/train_ml_model.py` | Train LightGBM model |

### Quick Commands

```powershell
# Rule-based deduplication
python scripts/run_dedupe.py --query-file query.sql --out results.csv

# ML-based deduplication
python scripts/run_dedupe.py --query-file query.sql --out results_ml.csv --use-ml-scoring --embeddings-dir models/embeddings

# Generate embeddings (GPU)
python scripts/build_embeddings.py --query-file query.sql --output-dir models/embeddings --device cuda

# Train ML model
python scripts/train_ml_model.py --results results.csv --query query.sql --embeddings models/embeddings --use-cv
```

---

## Source Structure

```
dubletten/
  dedupe/                   # Core library
    pipeline.py             # Main orchestration
    blocking.py             # Blocking strategies
    candidates.py           # Candidate pair generation
    scoring.py              # Rule-based scoring
    preprocessing.py        # Data normalization
    swisstopo.py           # Swiss address lookup
    ml/                     # ML components
      embeddings.py         # Sentence embeddings
      features.py           # Feature extraction (34 features)
      model.py              # LightGBM wrapper
      scoring_ml.py         # ML scorer
      calibration.py        # Probability calibration
      config.py             # ML configuration
    ml_training/            # Training pipeline
      silver_labels.py      # Weak supervision
      train.py              # Model training
  scripts/                  # CLI entry points
  tests/                    # Unit tests
  legacy/                   # Deprecated scripts
  docs/                     # Documentation
  models/                   # ML artifacts
```

---

## Technology Stack

### Core

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.8+ | Runtime |
| pandas | latest | Data processing |
| pyarrow | latest | Parquet I/O |
| numpy | latest | Numerical computing |

### ML

| Technology | Version | Purpose |
|------------|---------|---------|
| PyTorch | 2.5+ | Deep learning backend |
| sentence-transformers | 5.2+ | Semantic embeddings |
| LightGBM | 4.6+ | Gradient boosting model |
| faiss-cpu | latest | Similarity search |
| scikit-learn | latest | ML utilities |

### Matching

| Technology | Purpose |
|------------|---------|
| rapidfuzz | Fuzzy string matching |
| cologne-phonetics | German phonetic matching |

### Database

| Technology | Purpose |
|------------|---------|
| pyodbc | MSSQL connectivity |
| duckdb | Swisstopo reference database |

---

## Configuration

### Environment Variables

Create `.env` in project root:

```bash
DEDUPE_DB_SERVER=your_server
DEDUPE_DB_DATABASE=your_database
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--blocking-mode` | address | Blocking strategy (address/name) |
| `--fuzzy-threshold` | 0.80 | Minimum name similarity |
| `--window-size` | 10 | Sorted neighborhood window |
| `--use-ml-scoring` | false | Enable ML scoring |
| `--use-gpu` | false | GPU acceleration |
| `--chunksize` | 200000 | Processing batch size |

---

## Change Documentation

All significant changes are documented in `docs/stories/`. Recent changes:

| Date | Story |
|------|-------|
| 2026-01-07 | [add-gender-awareness-business-rule](stories/20260107165307-add-gender-awareness-business-rule.md) |
| 2026-01-06 | [improve-ml-entity-matching-quality](stories/20260106115922-improve-ml-entity-matching-quality.md) |
| 2026-01-04 | [add-gpu-inference-wsl-workflow](stories/20260104160500-add-gpu-inference-wsl-workflow.md) |
| 2026-01-04 | [batch-processing-gpu-inference](stories/20260104115000-batch-processing-gpu-inference.md) |
| 2026-01-04 | [fix-embeddings-save-memmap-windows](stories/20260104095000-fix-embeddings-save-memmap-windows.md) |
| 2026-01-03 | [ML_IMPLEMENTATION](stories/20260103100000-ML_IMPLEMENTATION.md) |

[View all stories](stories/)

---

## For AI Assistants

### Key Files to Read First

1. [dedupe/pipeline.py](../dedupe/pipeline.py) - Main entry point
2. [dedupe/scoring.py](../dedupe/scoring.py) - Rule-based matching logic
3. [dedupe/ml/scoring_ml.py](../dedupe/ml/scoring_ml.py) - ML integration
4. [dedupe/ml/features.py](../dedupe/ml/features.py) - Feature definitions

### Critical Patterns

1. **Always preserve business rule gates** - DOB, YOB, Zweitname checks
2. **Use batch processing** for ML scoring (50x faster than per-pair)
3. **Name-only embeddings** are critical for entity matching quality
4. **Calibrated probabilities** should be used for final scores

### Testing

```powershell
# Run tests
pytest tests/

# Run specific test
pytest tests/test_scoring.py -v
```

---

## External References

- [Swisstopo Address Data](https://www.swisstopo.admin.ch/) - Swiss reference addresses
- [sentence-transformers](https://www.sbert.net/) - Embedding models
- [LightGBM](https://lightgbm.readthedocs.io/) - Gradient boosting
- [rapidfuzz](https://maxbachmann.github.io/RapidFuzz/) - Fuzzy matching
