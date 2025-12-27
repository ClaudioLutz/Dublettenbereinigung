# Name2 Suffix Scoring Fix

## Problem

When comparing records where one has `name2` populated and the other has it as part of the combined `name` field, the scoring was too low (77.5%) even though they represent the same person.

### Example

```
Record A: Vorname="Hilde", Name="Haller", Name2="-Bensel"
Record B: Vorname="Hilde", Name="Haller-Bensel", Name2=""
```

After preprocessing:
```
Record A: first="hilde", last="haller", name2="bensel"
Record B: first="hilde", last="haller bensel", name2=""
```

The fuzzy match between "haller" and "haller bensel" only scored ~77.5%, even though these are clearly the same person (same first name, matching addresses).

## Solution

The fix combines the `name` and `name2` fields for comparison when:
1. One record has `name2` populated and the other doesn't
2. The `name2` value is a suffix of the other record's `name` field (validated by `check_zweitname`)

### Implementation

In `dedupe/scoring.py`, the `score_pair` function now creates normalized versions of the last names for comparison:

```python
# CRITICAL FIX: When name2 is present in one record but not the other,
# combine name+name2 for fair comparison
# Example: "Haller" + "Bensel" vs "Haller Bensel" should match 100%
last_i_for_comparison = last_i
last_j_for_comparison = last_j

if name2_i and not name2_j:
    # Combine last_i with name2_i if name2_i is a suffix of last_j
    if last_j.endswith(name2_i):
        last_i_for_comparison = (last_i + " " + name2_i).strip()
elif name2_j and not name2_i:
    # Combine last_j with name2_j if name2_j is a suffix of last_i
    if last_i.endswith(name2_j):
        last_j_for_comparison = (last_j + " " + name2_j).strip()
```

These combined names are then used throughout the scoring logic:
- Exact match detection
- Fuzzy name comparison
- Phonetic comparison

## Results

With the fix applied:
- **Before**: 77.5% confidence (fuzzy_normal)
- **After**: 100.0% confidence (exact_normal)
- **Improvement**: +22.5 percentage points

The match is now correctly identified as an exact match with maximum confidence.

## Test Coverage

New tests in `tests/test_name2_scoring.py` verify:
1. ✓ Name2 as suffix matches with high confidence (100%)
2. ✓ Different name2 values are correctly rejected
3. ✓ Both name2 empty works correctly

## Impact

This fix ensures that compound surnames split across `name` and `name2` fields are properly matched, preventing false negatives in the duplicate detection system.
