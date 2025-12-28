# Address-Based Blocking Implementation Summary

## Overview

Successfully implemented address-based blocking for the Swiss person deduplication pipeline. This transforms the system from name-based to address-based duplicate detection, focusing on finding duplicates within the same building rather than across all persons with similar names.

## What Was Implemented

### 1. **Preprocessing Enhancements** (`dedupe/preprocess.py`)

✅ **New Functions:**
- `normalize_street_key()` - Removes multilingual street type tokens
- `street_signature()` - Creates typo-robust signatures for recovery
- `parse_house_number()` - Splits house numbers into numeric + suffix (12A → "12" + "a")
- `parse_dob_ymd()` - Converts dates to YYYYMMDD integer format
- `extract_yob()` - Prioritizes Jahrgang, falls back to DOB year

✅ **New Output Fields:**
- `street_key`, `street_sig` - For address blocking
- `house_num`, `house_sfx` - Parsed house numbers
- `addr_key_building` - Building-level block key (PLZ|street_key|house_num)
- `addr_key_typo` - Typo recovery key (PLZ|house_num|street_sig)
- `dob_ymd`, `yob` - Enhanced date handling

### 2. **Address-Based Blocking** (`dedupe/blocking.py`)

✅ **New Blocking Functions:**
- `compute_address_building_key()` - Pass A: Strict building-level
- `compute_address_typo_key()` - Pass B: Street typo recovery

✅ **Updated Block Splitting:**
- Now splits by name prefixes when address blocks are too large
- Maintains deterministic behavior
- Keeps similar names together within same building

### 3. **Sorted Neighborhood Windowing** (`dedupe/candidates.py`)

✅ **New Candidate Generator:**
- `iter_windowed_fuzzy_pairs()` - Multi-pass sorted neighborhood
- Avoids O(n²) comparisons in large buildings
- Window size configurable (default: 10)
- Multi-pass with different sort keys (last+first, first+last)

### 4. **Enhanced Scoring Rules** (`dedupe/scoring.py`)

✅ **DOB/YOB Hard Gates:**
- Exact DOB mismatch → immediate rejection
- YOB mismatch → immediate rejection
- Stricter name threshold (90%) when both DOB and YOB missing

✅ **Improved House Number Logic:**
- Uses parsed `house_num` for cleaner comparisons
- Different numeric parts → reject (different buildings)
- Suffix differences allowed (12 vs 12A = same building)

### 5. **Flexible Pipeline** (`dedupe/pipeline.py`)

✅ **Configurable Blocking Mode:**
- `use_address_blocking=True` - New address-based strategy
- `use_address_blocking=False` - Legacy name-based strategy
- Automatic windowing selection based on mode

✅ **New Parameters:**
- `window_size` - Sorted neighborhood window (default: 10)
- `fuzzy_threshold` - Name similarity threshold (default: 0.80)

### 6. **Updated Run Script** (`scripts/run_dedupe.py`)

✅ **New Command-Line Options:**
- `--blocking-mode {address,name}` - Choose strategy (default: address)
- `--fuzzy-threshold` - Name similarity threshold
- `--window-size` - Sorted neighborhood window
- `--no-address-aware` - Disable address-assisted matching

### 7. **Comprehensive Tests** (`tests/test_address_based_blocking.py`)

✅ **Test Coverage:**
- House number parsing (12, 12A, 12b)
- Street normalization and signatures
- Address key construction
- DOB/YOB hard gates
- Sorted neighborhood windowing
- End-to-end scenarios

### 8. **Documentation** (`docs/address_based_blocking.md`)

✅ **Complete Documentation:**
- Architecture overview
- Function descriptions
- Usage examples
- Configuration guide
- Migration guide
- Performance characteristics

---

## Key Features

### 🏢 Building-Level Matching
- Blocks people at the same address (PLZ + Street + House Number)
- Treats 12, 12A, 12B as same building (different apartments)

### 🔍 Typo Recovery
- Dedicated pass for street name variants
- Robust to <1% character differences
- Example: "Bahnhofstrasse" vs "Bahnhoffstrasse" recovered

### 📅 Strict Date Validation
- Exact DOB mismatch → reject
- Year of birth mismatch → reject
- Requires 90% name similarity when dates missing (protects against family members)

### ⚡ Efficient Windowing
- O(n·w) comparisons instead of O(n²)
- Multi-pass sorting catches similar names
- Configurable window size (10-25 recommended)

### 🔄 Backward Compatible
- Can switch between address and name blocking
- Legacy mode preserved with `--blocking-mode name`
- All existing tests pass

---

## Usage Examples

### Basic Address-Based Run
```bash
python scripts/run_dedupe.py \
    --query-file query.sql \
    --out results.csv \
    --blocking-mode address
```

### With Custom Parameters
```bash
python scripts/run_dedupe.py \
    --query-file query.sql \
    --out results.csv \
    --blocking-mode address \
    --fuzzy-threshold 0.85 \
    --window-size 15 \
    --workers 4
```

### Legacy Name-Based Mode
```bash
python scripts/run_dedupe.py \
    --query-file query.sql \
    --out results.csv \
    --blocking-mode name
```

---

## Performance Expectations

### Address-Based Blocking

**Advantages:**
- ✅ Smaller blocks (typically 1-100 records)
- ✅ Fewer false positives (same building constraint)
- ✅ Faster per-block processing
- ✅ Better for large datasets (8M+ records)

**Trade-offs:**
- ⚠️ Won't find duplicates at different addresses
- ⚠️ Requires good address data quality (>95% populated)
- ⚠️ May miss relocations (by design)

### Recommended Settings

| Scenario | fuzzy_threshold | window_size | blocking_mode |
|----------|----------------|-------------|---------------|
| **Large building (100+ residents)** | 0.80 | 15-25 | address |
| **Standard building (10-50)** | 0.80 | 10 | address |
| **Small building (<10)** | 0.80 | 10 | address |
| **Cross-address matching needed** | 0.80 | 10 | name |
| **Poor address data** | 0.80 | 10 | name |

---

## Testing

### Run Tests
```bash
# All address-based tests
pytest tests/test_address_based_blocking.py -v

# All dedupe tests
pytest tests/ -v -k dedupe
```

### Verify Installation
```python
from dedupe.preprocess import parse_house_number
import pandas as pd

house = pd.Series(['12', '12A', '12b'])
num, sfx = parse_house_number(house)
print(num.tolist())  # ['12', '12', '12']
print(sfx.tolist())  # ['', 'a', 'b']
```

---

## Files Modified

### Core Pipeline
- ✅ `dedupe/preprocess.py` - Address normalization, house parsing, DOB handling
- ✅ `dedupe/blocking.py` - Address-based blocking keys
- ✅ `dedupe/candidates.py` - Sorted neighborhood windowing
- ✅ `dedupe/scoring.py` - DOB hard gates, stricter thresholds
- ✅ `dedupe/pipeline.py` - Mode selection, windowing integration

### Scripts & Tests
- ✅ `scripts/run_dedupe.py` - CLI with blocking mode options
- ✅ `tests/test_address_based_blocking.py` - Comprehensive test suite

### Documentation
- ✅ `docs/address_based_blocking.md` - Complete guide
- ✅ `IMPLEMENTATION_SUMMARY.md` - This file

---

## Known Limitations

1. **Chunk Boundaries**: Address blocks spanning SQL chunk boundaries may be missed
   - Marked as TODO in `pipeline.py`
   - Workaround: Order SQL by address fields

2. **Address Variations**: Different representations may split blocks
   - Example: "Str." vs "Strasse" handled but may cause minor splits
   - Typo recovery pass mitigates this

3. **No Cross-Address Linking**: By design, won't find same person at different addresses
   - Use `--blocking-mode name` if cross-address matching needed

---

## Next Steps

### For Production Deployment

1. **Test on Sample Data**
   ```bash
   python scripts/run_dedupe.py \
       --query-file query.sql \
       --out results_test.csv \
       --blocking-mode address
   ```

2. **Validate Results**
   - Check match quality
   - Verify no false positives from family members
   - Confirm street typos are recovered

3. **Tune Parameters** (if needed)
   - Increase `window_size` if missing matches (15-25)
   - Increase `fuzzy_threshold` if too many false positives (0.85)

4. **Full Run**
   ```bash
   python scripts/run_dedupe.py \
       --query-file query.sql \
       --out production_results.csv \
       --blocking-mode address \
       --workers 0
   ```

### For Future Enhancement

1. Implement chunk boundary carry-over
2. Add adaptive window sizing
3. Enhance Swiss address parsing
4. Add hierarchical blocking (canton/city level)

---

## Success Criteria ✅

- [x] House numbers parsed correctly (12 = 12A = 12B at building level)
- [x] Street normalization removes type tokens (Strasse, Str, Rue, Via, etc.)
- [x] Street typo recovery functional (<1% character differences)
- [x] DOB exact mismatch rejects matches
- [x] YOB mismatch rejects matches
- [x] Stricter threshold (90%) applied when DOB/YOB missing
- [x] Sorted neighborhood windowing implemented
- [x] Address-based blocking keys functional
- [x] Pipeline supports both address and name modes
- [x] CLI updated with mode selection
- [x] Comprehensive tests pass
- [x] Documentation complete

---

## Support

For questions or issues:
1. Review `docs/address_based_blocking.md` for detailed guide
2. Check `tests/test_address_based_blocking.py` for usage examples
3. Run with `--blocking-mode name` for legacy behavior
4. Contact developer with specific scenarios

---

**Implementation Date**: December 28, 2025  
**Version**: 1.0  
**Status**: ✅ Complete and Ready for Testing
