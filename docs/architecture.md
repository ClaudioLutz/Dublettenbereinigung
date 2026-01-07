# Dubletten Architecture Documentation

> **Generated:** 2026-01-06 | **Scan Level:** Exhaustive | **Project Type:** Data Pipeline + ML

---

## Executive Summary

**Dubletten** is a Swiss entity deduplication pipeline designed to identify duplicate records in address databases containing 7.5M+ records. The system combines rule-based fuzzy matching with ML-enhanced scoring to achieve high precision (97-98%) and recall (85-90%).

**Key Architectural Decisions:**
1. **Blocking-first strategy** - Reduces O(n^2) comparisons to manageable candidate pairs
2. **Dual scoring modes** - Rule-based (fast, interpretable) + ML-based (higher accuracy)
3. **Weak supervision** - ML model trained on high-confidence rule-based matches
4. **GPU acceleration** - Optional CUDA support for embeddings and inference

---

## System Architecture

```
                    +-----------------+
                    |   Data Source   |
                    | (MSSQL/Parquet) |
                    +--------+--------+
                             |
                             v
                    +--------+--------+
                    |  Preprocessing  |
                    | - Normalization |
                    | - Address lookup|
                    +--------+--------+
                             |
                             v
                    +--------+--------+
                    |    Blocking     |
                    | - Address-based |
                    | - Name-based    |
                    +--------+--------+
                             |
                             v
                    +--------+--------+
                    |   Candidates    |
                    | - Pair gen      |
                    | - Deduplication |
                    +--------+--------+
                             |
            +----------------+----------------+
            |                                 |
            v                                 v
    +-------+-------+               +---------+---------+
    |  Rule-Based   |               |    ML-Based       |
    |   Scoring     |               |    Scoring        |
    | - Fuzzy match |               | - 34 features     |
    | - Business    |               | - LightGBM        |
    |   rules       |               | - Calibration     |
    +-------+-------+               +---------+---------+
            |                                 |
            +----------------+----------------+
                             |
                             v
                    +--------+--------+
                    |    Results      |
                    | - CSV output    |
                    | - Match scores  |
                    +-----------------+
```

---

## Core Components

### 1. Pipeline Module (`dedupe/pipeline.py`)

**Purpose:** Main orchestration of the deduplication workflow.

**Key Functions:**
- `run_pipeline()` - Entry point coordinating all stages
- Chunk-based processing for memory efficiency
- Progress tracking and timing

**Configuration:**
- `chunksize`: Records per processing batch (default: 200,000)
- `workers`: Parallel workers (0 = auto-detect)
- `use_address_blocking`: Blocking strategy selection

### 2. Blocking Module (`dedupe/blocking.py`)

**Purpose:** Generate candidate pairs efficiently using blocking keys.

**Blocking Strategies:**

| Strategy | Key Pattern | Use Case |
|----------|-------------|----------|
| Address-based | PLZ + street_sig + house_num | Default, most efficient |
| Name-based | surname_soundex + first_initial | Legacy, broader recall |

**Key Functions:**
- `generate_blocking_keys()` - Create blocking keys per record
- `sorted_neighborhood()` - Window-based pair generation

### 3. Scoring Module (`dedupe/scoring.py`)

**Purpose:** Rule-based entity matching with business logic.

**Key Class:** `MatchResult`
- `i`, `j`: Record indices
- `score`: Confidence (0-100)
- `name_score`, `addr_score`: Component scores
- `reason`: Match type (exact_normal, fuzzy_swapped, etc.)

**Business Rule Gates:**
1. **DOB Gate** - Reject if both have different dates of birth
2. **YOB Gate** - Reject if both have different birth years
3. **Zweitname Gate** - Reject on second name conflicts

**Match Types:**
- `exact_normal` / `exact_swapped` - Exact name match
- `fuzzy_normal` / `fuzzy_swapped` - Fuzzy name match (>80%)
- `address_assisted` - Borderline names + strong address
- `phonetic_assisted` - Cologne phonetic fallback

### 4. ML Scoring Module (`dedupe/ml/scoring_ml.py`)

**Purpose:** ML-enhanced scoring with calibrated probabilities.

**Key Class:** `MLScorer`
- Drop-in replacement for rule-based `score_pair()`
- Business rule gates preserved
- Batch processing for performance

**Configuration:**
- `min_name_similarity`: Gate threshold (default: 0.50)
- `use_gpu`: Enable GPU inference
- `fallback_to_rules`: Fallback on ML errors

**Match Types:**
- `ml_high_confidence_exact` - Prob >= 95%, exact DOB
- `ml_high_confidence_address` - Prob >= 95%, strong address
- `ml_medium_confidence_semantic` - Embedding-based
- `ml_medium_confidence_phonetic` - Phonetic match

### 5. Feature Extraction (`dedupe/ml/features.py`)

**Purpose:** Extract 34 features for ML model.

**Feature Categories:**

| Category | Features | Count |
|----------|----------|-------|
| Name similarity | WRatio normal/swapped, first/last | 8 |
| Phonetic | Cologne first/last match | 2 |
| Name2/Zweitname | present_both, conflict | 2 |
| Address | PLZ, house, street, ort, composite | 8 |
| Date/Birth | DOB exact, YOB exact, quality flags | 6 |
| Embeddings (full) | cosine, L2, dot, manhattan | 4 |
| Embeddings (name) | cosine, L2, dot, manhattan | 4 |
| Interaction | name*addr, first_word_bonus | 2 |

**Total:** 34 features

### 6. Embeddings Module (`dedupe/ml/embeddings.py`)

**Purpose:** Generate semantic embeddings using sentence-transformers.

**Classes:**
- `EmbeddingGenerator` - Create embeddings from text
- `EmbeddingStore` - Store and retrieve embeddings

**Configuration (from `config.py`):**
- `EMBEDDING_MODEL`: "all-MiniLM-L6-v2"
- `EMBEDDING_DIM`: 384
- `BATCH_SIZE`: 256
- `DEVICE`: "auto" (CUDA if available)

**Text Templates:**
- Full: `[NAME] {first} {last} {name2} [ADDR] {street} {house} {plz} {ort}`
- Name-only: `[NAME] {first} {last} {name2}`

---

## Data Flow

### Phase 1: Preprocessing

```python
# Input: Raw DataFrame from SQL/Parquet
df = preprocess(df)
# Output: Normalized columns (first, last, name2, street, house, plz, ort)
```

**Key Normalizations:**
- Lowercase, strip whitespace
- PLZ6 to PLZ4 conversion
- House number parsing (num + suffix)
- Street signature (typo recovery)
- Swisstopo reference lookup (optional)

### Phase 2: Blocking

```python
# Input: Preprocessed DataFrame
blocking_keys = generate_blocking_keys(df, strategy="address")
# Output: Dict[key, List[int]] mapping keys to record indices
```

**Address-based Key:** `{plz4}_{street_sig}_{house_num}`
**Name-based Key:** `{surname_soundex}_{first_initial}`

### Phase 3: Candidate Generation

```python
# Input: Blocking keys
candidates = generate_candidates(blocking_keys, window_size=10)
# Output: List[(i, j)] of candidate pairs
```

Uses sorted neighborhood within blocks to further reduce pairs.

### Phase 4: Scoring

```python
# Rule-based
result = score_pair(i, j, cols, fuzzy_threshold=0.80)

# ML-based
result = ml_scorer.score_pair(i, j, cols)
# or batch:
results = ml_scorer.score_batch(pairs, cols)
```

### Phase 5: Output

```python
# Output: CSV with columns
# i, j, score, name_score, addr_score, reason, is_swapped, [record fields]
results.to_csv(out_path)
```

---

## ML Pipeline

### Training Workflow

```
                    +-----------------+
                    | Rule-Based      |
                    | Results (CSV)   |
                    +--------+--------+
                             |
                             v
                    +--------+--------+
                    | Silver Label    |
                    | Generation      |
                    | - score >= 95   |
                    | - DOB match     |
                    +--------+--------+
                             |
                             v
                    +--------+--------+
                    | Feature         |
                    | Extraction      |
                    | (34 features)   |
                    +--------+--------+
                             |
                             v
                    +--------+--------+
                    | LightGBM        |
                    | Training        |
                    | + Cross-Val     |
                    +--------+--------+
                             |
                             v
                    +--------+--------+
                    | Calibration     |
                    | (Isotonic)      |
                    +--------+--------+
                             |
                             v
                    +--------+--------+
                    | Model Artifacts |
                    | - .txt, .pkl    |
                    +-----------------+
```

### Model Artifacts

```
models/
  lightgbm/
    matcher_v1.txt        # LightGBM model
    matcher_v1_metadata.json
    calibrator_v1.pkl     # Isotonic regression
  embeddings/
    embeddings_v1.dat     # Memory-mapped (11.5 GB)
    embeddings_v1_meta.npz
    embeddings_v1_name.dat  # Name-only embeddings
    faiss_index_v1.bin    # Optional similarity index
```

---

## Configuration

### Environment Variables (`.env`)

```bash
DEDUPE_DB_SERVER=<server>
DEDUPE_DB_DATABASE=<database>
```

### ML Configuration (`dedupe/ml/config.py`)

```python
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
BATCH_SIZE = 256
DEVICE = "auto"
MODEL_VERSION = "v1"
```

### Pipeline Configuration (CLI)

| Flag | Default | Description |
|------|---------|-------------|
| `--blocking-mode` | address | Blocking strategy |
| `--fuzzy-threshold` | 0.80 | Minimum name similarity |
| `--window-size` | 10 | Sorted neighborhood window |
| `--use-ml-scoring` | false | Enable ML scoring |
| `--use-gpu` | false | Enable GPU acceleration |
| `--chunksize` | 200000 | Processing batch size |

---

## Performance Characteristics

### Processing Speed

| Component | CPU | GPU |
|-----------|-----|-----|
| Embeddings | ~1,000 rec/s | ~5,000 rec/s |
| Rule-based scoring | ~8,000 pairs/s | N/A |
| ML scoring | ~6,500 pairs/s | ~30,000 pairs/s |

### Memory Usage

| Component | RAM |
|-----------|-----|
| Loaded embeddings | ~300 MB |
| Model | ~50 MB |
| Peak processing | ~2 GB |

### Disk Usage

| Artifact | Size |
|----------|------|
| Full embeddings | 11.5 GB |
| Name embeddings | 11.5 GB |
| LightGBM model | <1 MB |

---

## Extension Points

### Adding New Features

1. Add feature to `FEATURE_NAMES` in `features.py`
2. Implement extraction in appropriate `_extract_*_features()` method
3. Retrain model with new features

### Adding New Blocking Strategy

1. Implement key generation in `blocking.py`
2. Add strategy option to `--blocking-mode` in CLI
3. Update pipeline to use new strategy

### Adding New Business Rules

1. Implement rule check in `check_business_rule_violations()` in `features.py`
2. Optionally add corresponding feature for ML model

---

## Dependencies Graph

```
dedupe/
  pipeline.py
    -> preprocessing.py
    -> blocking.py
    -> candidates.py
    -> scoring.py (rule-based)
    -> ml/scoring_ml.py (ML-based)

dedupe/ml/
  scoring_ml.py
    -> features.py
    -> model.py
    -> calibration.py
    -> embeddings.py

dedupe/ml_training/
  train.py
    -> silver_labels.py
    -> features.py
```

---

## Glossary

| Term | Definition |
|------|------------|
| Blocking | Technique to reduce candidate pairs by grouping similar records |
| Candidate pair | Two records potentially representing the same entity |
| Crefo | Swiss company registration number |
| DOB | Date of Birth (YYYYMMDD format) |
| YOB | Year of Birth |
| PLZ | Swiss postal code (4 or 6 digits) |
| Zweitname | Second/maiden name |
| Name swapping | First/last name fields reversed |
| Cologne phonetics | German phonetic algorithm for name matching |
| Weak supervision | Training labels derived from rule-based system |
| Calibration | Adjusting raw scores to true probabilities |

---

## References

- [GETTING_STARTED_ML.md](../GETTING_STARTED_ML.md) - Quick start guide
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) - Detailed system design
- [businessrules.md](businessrules.md) - Business rule documentation
- [docs/stories/](stories/) - Change documentation
