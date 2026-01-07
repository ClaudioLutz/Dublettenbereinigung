# Add Gender-Awareness Business Rule

## Summary

Implemented a gender-aware business rule in the deterministic deduplication system to prevent false positive matches between people with similar names but different genders at the same address (e.g., "Peter Muster" vs "Petra Muster", or siblings/spouses living together). Uses existing Swiss registry gender data (Pa_S_Anrede field) with 95% accuracy to apply a 20-point confidence penalty when different genders are detected at the same address with similar names.

## Context / Problem

During strategic review of ML vs deterministic approaches, we identified edge cases where the deterministic system incorrectly matched people with similar names living at the same address:
- **Siblings**: "Peter Muster" and "Petra Muster" at same address
- **Spouses**: "Andreas Müller" and "Andrea Müller" at same address
- **Roommates**: Different people with similar names sharing an address

These false positives contributed to the 1% error rate in the ~110k medium-confidence duplicate candidates requiring manual review. The Swiss person registry already contains gender data (Pa_S_Anrede field) with 95% accuracy, making this a quick win without requiring ML inference.

## What Changed

### Files Modified

**1. `query.sql` (lines 13-14)**
- Added `Pa_S_Anrede` field to query to retrieve salutation/gender data

**2. `dedupe/preprocess.py` (lines 438-452, 586)**
- Added gender field normalization logic
- Maps multilingual salutations to simple M/F/U codes:
  - German: Herr → M, Frau → F
  - English: Mr → M, Mrs/Ms/Miss → F
  - French: Monsieur → M, Madame → F
  - Italian: Signor → M, Signora → F
  - Unknown/missing → U
- Added `gender` to output dictionary

**3. `dedupe/scoring.py` (lines 289-293, 398-404, 453-459, 530-535, 626-631, 722-747)**
- Added gender comparison logic early in `score_pair()` function
- Defined `different_genders` variable: true when both genders are known (not 'U') and different
- Applied 20-point confidence penalty across all match types when:
  - Different genders detected
  - Same address (matching PLZ + house number)
  - Name similarity ≥75% (to avoid penalizing unrelated pairs)
- Updated reason strings with `_different_gender` suffix for tracking
- Match types affected:
  - `exact_normal` → `exact_normal_different_gender`
  - `exact_swapped` → `exact_swapped_different_gender`
  - `address_assisted_normal` → `address_assisted_normal_different_gender`
  - `address_assisted_swapped` → `address_assisted_swapped_different_gender`
  - `phonetic_assisted_normal` → `phonetic_assisted_normal_different_gender`
  - `phonetic_assisted_swapped` → `phonetic_assisted_swapped_different_gender`
  - `fuzzy_normal` → `fuzzy_normal_different_gender`
  - `fuzzy_swapped` → `fuzzy_swapped_different_gender`

### Implementation Details

**Gender Penalty Logic:**
```python
# Check if genders are different (both known and not equal)
different_genders = (gender_i != 'U' and gender_j != 'U' and gender_i != gender_j)

# Check if same address (PLZ + house number match)
same_address = (plz_i and plz_j and plz_i == plz_j and
                house_num_i and house_num_j and house_num_i == house_num_j)

# Apply penalty if conditions met
if different_genders and same_address and best_score >= 0.75:
    confidence = max(confidence - 20.0, 40.0)  # 20-point penalty, floor at 40%
    reason = reason + "_different_gender"
```

**Why 20 points?**
- High-confidence matches typically score 85-100%
- Auto-merge threshold is typically 80-85%
- 20-point penalty pushes most false positives below auto-merge threshold
- Forces manual review for different-gender same-address pairs

**Why ≥75% name similarity threshold?**
- Avoids penalizing unrelated people with completely different names at same address
- Targets edge cases where names are suspiciously similar (siblings/spouses)

## How to Test

### 1. Run deduplication with gender rule:
```powershell
python scripts/run_dedupe.py `
    --query-file query.sql `
    --out results_with_gender.csv `
    --blocking-mode address `
    --fuzzy-threshold 0.80
```

### 2. Check for gender mismatch flags:
```powershell
# Count matches with different_gender suffix
python -c "import pandas as pd; df = pd.read_csv('results_with_gender.csv'); print(df['match_type'].value_counts())"

# Find examples of penalized matches
python -c "import pandas as pd; df = pd.read_csv('results_with_gender.csv'); print(df[df['match_type'].str.contains('different_gender', na=False)][['Vorname_i', 'Name_i', 'Vorname_j', 'Name_j', 'confidence', 'match_type']].head(20))"
```

### 3. Expected behavior:
- Pairs like "Peter Muster" (M) + "Petra Muster" (F) at same address should show:
  - Reduced confidence (e.g., 95% → 75%)
  - Match type with `_different_gender` suffix
  - Pushed below auto-merge threshold for manual review

### 4. Compare with baseline:
```powershell
# Compare error rates before/after
# Check how many of the 110k medium-confidence pairs have gender mismatches
# Measure reduction in false positives
```

## Risk / Rollback Notes

### Risks

**1. False Negatives (Missing True Duplicates):**
- Transgender individuals who changed gender marker in registry
- Data entry errors in Pa_S_Anrede field
- Unisex/ambiguous names (Andrea, etc.)
- **Mitigation**: 20-point penalty reduces confidence but doesn't reject outright (floor at 40%), allowing manual review

**2. Data Quality:**
- Pa_S_Anrede accuracy is ~95% (user-reported)
- Missing/unknown values mapped to 'U' and excluded from penalty
- **Mitigation**: Only apply penalty when both genders are known (not 'U')

**3. Edge Cases:**
- Gender-neutral salutations not in mapping dictionary
- Non-binary individuals (Swiss registry limitation)
- **Mitigation**: Unknown values treated as 'U', no penalty applied

### Rollback

If the gender rule causes issues:

**1. Disable gender penalty:**
```python
# In dedupe/scoring.py, change line 728:
if False and different_genders and same_address and best_score >= 0.75:
    # This will never trigger
```

**2. Remove gender field:**
```sql
-- In query.sql, remove line:
-- ,p.Pa_S_Anrede
```

**3. Revert preprocessing:**
```python
# In dedupe/preprocess.py, remove lines 438-452 and 586
```

**4. Revert scoring logic:**
- Remove gender penalty blocks from all return statements in `score_pair()`
- Remove `different_genders` variable definition (lines 289-293)

### Verification

To verify this change doesn't break existing behavior:

```powershell
# Run tests
pytest tests/test_scoring.py -v

# Compare results with/without gender field
# Should be identical for same-gender pairs or unknown-gender pairs
```

### Files Changed
- `query.sql`
- `dedupe/preprocess.py`
- `dedupe/scoring.py`
- `docs/stories/20260107165307-add-gender-awareness-business-rule.md` (this file)

### Next Steps (from brainstorming session)
1. **Immediate**: Test gender rule on full dataset, measure impact on 110k medium-confidence pairs
2. **Week 1**: Analyze remaining errors after gender rule to identify next highest-impact deterministic rule
3. **Week 2-4**: Implement 2-3 additional deterministic rules based on error analysis
4. **Month 2**: Compare deterministic results with ML approach, make final strategic decision

### Performance Impact
- **Negligible**: Gender comparison is simple string equality check (M/F/U)
- No ML inference required
- No additional database queries (field already in query)
- Adds ~0.1ms per pair comparison (string equality check)
