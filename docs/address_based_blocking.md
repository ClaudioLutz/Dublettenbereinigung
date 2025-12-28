# Address-Based Blocking for Person Deduplication

## Overview

This document describes the **address-based blocking** implementation for the Swiss person deduplication pipeline. This new approach finds duplicates within the same building/address rather than across all persons with similar names.

### Key Changes from Name-Based Blocking

| Aspect | Name-Based (Legacy) | Address-Based (New) |
|--------|---------------------|---------------------|
| **Primary block key** | Name prefix + PLZ + Year | PLZ + Street + House Number |
| **Comparison scope** | People with similar names anywhere | People at the same address |
| **House number handling** | Simple string comparison | Parsed numeric part (12 = 12A = 12B) |
| **Street typo handling** | Limited | Dedicated typo recovery pass |
| **DOB validation** | Year-only comparison | Full DOB + YOB with hard gates |
| **Candidate generation** | All-pairs or process.extract | Sorted neighborhood windowing |
| **Family protection** | Year-based only | Requires 90% name match when no DOB |

---

## Architecture

### 1. Preprocessing (dedupe/preprocess.py)

#### New Functions

**`normalize_street_key(street)`**
- Removes multilingual street type tokens (strasse, str, rue, via, etc.)
- Creates normalized key for strict blocking
- Example: "Bahnhofstrasse" → "bahnhof"

**`street_signature(street)`**
- Generates typo-robust signature
- Takes first 4 chars of each token, sorts, joins with "-"
- Example: "Bahnhofstrasse" → "bahn", "Bahnhoffstrasse" → "bahn" (same signature)

**`parse_house_number(house)`**
- Splits into numeric core and alphabetic suffix
- Returns: (house_num, house_sfx)
- Example: "12A" → ("12", "a")

**`parse_dob_ymd(date_series)`**
- Converts dates to YYYYMMDD integer format
- Returns -1 for missing/invalid dates

**`extract_yob(dob_ymd, jahrgang)`**
- Prioritizes Jahrgang if available
- Falls back to DOB year
- Returns -1 if both missing

#### New Columns in Preprocessed Output

- `street_key`: Normalized street name for blocking
- `street_sig`: Typo-robust signature
- `house_num`: Numeric part of house number (building level)
- `house_sfx`: Alphabetic suffix (apartment level)
- `addr_key_building`: PLZ|street_key|house_num
- `addr_key_typo`: PLZ|house_num|street_sig
- `dob_ymd`: Full date of birth (YYYYMMDD)
- `yob`: Year of birth (from Jahrgang or DOB)

---

### 2. Blocking (dedupe/blocking.py)

#### New Functions

**`compute_address_building_key(cols)`**
- Pass A: Strict building-level blocking
- Key format: `PLZ|street_key|house_num`
- Example: `8000|bahnhof|12`

**`compute_address_typo_key(cols)`**
- Pass B: Typo recovery
- Key format: `PLZ|house_num|street_sig`
- Example: `8000|12|bahn`

#### Updated Oversized Block Splitting

When an address block exceeds `max_block_size`, it's split by:
1. **Primary split**: Last name prefix (3 chars) + First name prefix (1 char)
2. **Secondary split**: Last name prefix (2 chars) + First name prefix (2 chars)
3. **Fallback**: Deterministic chunking

This keeps similar names together within the same building.

---

### 3. Candidate Generation (dedupe/candidates.py)

#### New Function: Sorted Neighborhood Windowing

**`iter_windowed_fuzzy_pairs(idx, cols, window=10, name_threshold=88)`**

Instead of comparing all pairs or using `process.extract()`, this implements:

1. **Multi-pass sorting**: Sort by different name orders
   - Pass 1: `last_full|first` (catches similar surnames)
   - Pass 2: `first|last_full` (swap-friendly)

2. **Sliding window**: Each record compares with next `window` neighbors

3. **Name prefilter**: Only yields pairs above `name_threshold`

**Benefits**:
- Avoids O(n²) in large buildings
- Still catches similar names via multi-pass
- Deterministic and reproducible

---

### 4. Scoring (dedupe/scoring.py)

#### New Hard Gates

**DOB Exact Mismatch**
```python
if dob_i != -1 and dob_j != -1 and dob_i != dob_j:
    return None  # Reject
```

**YOB Mismatch**
```python
if yob_i != -1 and yob_j != -1 and yob_i != yob_j:
    return None  # Reject
```

#### Stricter Threshold for Missing DOB/YOB

When both DOB and YOB are missing:
```python
effective_fuzzy_threshold = max(fuzzy_threshold, 0.90)
```

This prevents matching family members (e.g., father and son) with the same surname at the same address when we have no birth date information.

#### House Number Comparison

Uses parsed `house_num` for cleaner logic:
```python
if house_num_i and house_num_j and house_num_i != house_num_j:
    return None  # Different buildings
```

---

### 5. Pipeline (dedupe/pipeline.py)

#### Updated `run_pipeline()` Parameters

- **`use_address_blocking`**: Enable address-based (True) or name-based (False)
- **`window_size`**: Window size for sorted neighborhood (default: 10)

#### Blocking Strategy Selection

**Address-based mode** (`use_address_blocking=True`):
- Pass A: `compute_address_building_key()`
- Pass B: `compute_address_typo_key()`
- Uses windowed candidate generation

**Name-based mode** (`use_address_blocking=False`):
- Pass A: `compute_primary_key()` (legacy)
- Pass B: `compute_swap_invariant_key()` (legacy)
- Uses process.extract candidate generation

#### TODO: Chunk Boundary Handling

For large datasets with chunked SQL reads, a "carry-over" mechanism is needed to handle address blocks that span chunk boundaries. Currently marked as TODO in the code.

---

## Usage

### Command Line

```bash
# Address-based blocking (default)
python scripts/run_dedupe.py --query-file query.sql --out results.csv

# With custom parameters
python scripts/run_dedupe.py \
    --query-file query.sql \
    --out results.csv \
    --blocking-mode address \
    --fuzzy-threshold 0.80 \
    --window-size 10 \
    --workers 4

# Legacy name-based blocking
python scripts/run_dedupe.py \
    --query-file query.sql \
    --out results.csv \
    --blocking-mode name
```

### Programmatic

```python
from dedupe.pipeline import run_pipeline
from dedupe.config import DbConfig

run_pipeline(
    query=sql_query,
    db_cfg=DbConfig.from_env(),
    out_path="results.csv",
    use_address_blocking=True,  # New address-based mode
    window_size=10,
    fuzzy_threshold=0.80,
    enable_address_aware=True
)
```

---

## Configuration Parameters

### Blocking Parameters

- **`max_block_size`**: Maximum block size before splitting (default: 2000)
- **`small_block_all_pairs`**: Threshold for all-pairs comparison (default: 400)

### Candidate Generation

- **`window_size`**: Sorted neighborhood window size (default: 10)
  - Larger = more comparisons, better recall
  - Smaller = faster, may miss distant similar names
  - Recommended: 10-25 for large buildings

- **`name_threshold`**: Minimum name similarity for candidate generation (default: 88)
  - Used as prefilter in windowed pairs
  - Does not affect final scoring

### Scoring

- **`fuzzy_threshold`**: Base fuzzy matching threshold (default: 0.80)
  - Automatically raised to 0.90 when DOB/YOB missing

---

## Performance Characteristics

### Address-Based vs Name-Based

| Metric | Name-Based | Address-Based |
|--------|-----------|---------------|
| **Block size** | Large (100-10,000s) | Small (1-100) |
| **Comparisons per block** | O(n²) or O(n·k) | O(n·w) |
| **False positives** | Higher (name matches across city) | Lower (same building only) |
| **False negatives** | Lower (finds all name matches) | Higher (may miss if address differs) |
| **Street typo tolerance** | Implicit in fuzzy matching | Explicit typo recovery pass |

### Recommended Use Cases

**Address-based blocking** is best when:
- ✅ You want to find duplicates **at the same address**
- ✅ Address data quality is good (>95% populated)
- ✅ Goal is finding person duplicates, not linking across moves
- ✅ Large datasets where name-based blocks are too big

**Name-based blocking** is better when:
- ✅ You need to find duplicates **across addresses**
- ✅ Address data is poor or inconsistent
- ✅ Goal is tracking people across relocations
- ✅ Small to medium datasets (<1M records)

---

## Testing

Run the address-based blocking tests:

```bash
pytest tests/test_address_based_blocking.py -v
```

Test coverage includes:
- House number parsing (12, 12A, 12B)
- Street normalization and signatures
- Address key construction
- DOB/YOB hard gates
- Sorted neighborhood windowing
- End-to-end scenarios

---

## Migration Guide

### From Name-Based to Address-Based

1. **Ensure SQL query includes required fields**:
   - `Plz` (postal code)
   - `Strasse` (street name)
   - `HausNummer` (house number)
   - `Geburtstag` or `Jahrgang` (date/year of birth)

2. **SQL query should order by address** (recommended):
   ```sql
   ORDER BY Plz, Strasse, HausNummer
   ```

3. **Update run command**:
   ```bash
   # Old (name-based)
   python scripts/run_dedupe.py --query-file query.sql --out results.csv
   
   # New (address-based, explicit)
   python scripts/run_dedupe.py --query-file query.sql --out results.csv --blocking-mode address
   ```

4. **Adjust thresholds if needed**:
   - Start with defaults (`fuzzy_threshold=0.80`, `window_size=10`)
   - If too many false positives → increase `fuzzy_threshold` to 0.85
   - If missing matches → increase `window_size` to 15-25

### Backward Compatibility

The pipeline maintains backward compatibility:
- Set `--blocking-mode name` to use legacy behavior
- Default is now `address` mode for new deployments

---

## Known Limitations

1. **Chunk boundaries**: Address blocks spanning SQL chunk boundaries may be missed (TODO)
2. **Address variations**: Different representations of same address (e.g., "Str." vs "Strasse") are handled but may split blocks
3. **Missing addresses**: Records without address data won't be blocked effectively
4. **Relocation tracking**: Won't find same person at different addresses (by design)

---

## Future Enhancements

1. **Chunk boundary carry-over**: Implement proper handling of blocks spanning chunks
2. **Adaptive windowing**: Adjust window size based on block characteristics
3. **Address parsing**: More sophisticated parsing of Swiss addresses
4. **Hierarchical blocking**: Add city/canton level for regional deduplication

---

## References

- Implementation plan: `docs/Deduplication Pipeline for Swiss Person Records_ Implementation Guide.pdf`
- Business rules: `docs/dedupe_business_rules_implementation.md`
- Test suite: `tests/test_address_based_blocking.py`
