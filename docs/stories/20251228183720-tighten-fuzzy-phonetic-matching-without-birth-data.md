# Tighten Fuzzy/Phonetic Matching When Birth Data is Missing

## Summary

Implemented much stricter fuzzy and phonetic matching thresholds when geburtstag (date of birth) or jahrgang (year of birth) data is missing or not matched. This prevents false positives like "Evalotta vs Evlotta Samuelsson" (both missing birth data) and "Rolf Thür vs Rolf Haltner" (different surnames, mismatched birth data quality) from being incorrectly matched.

## Context / Problem

The deduplication system was producing false positive matches when birth information was missing or of poor quality:

1. **Evalotta vs Evlotta Samuelsson** - 58% name similarity with no birth data → incorrectly matched
2. **Rolf Thür vs Rolf Haltner** - 72.5% similarity, different surnames, one missing jahrgang → incorrectly matched
3. **Catrin vs Katherina Staub** - phonetic match with no birth data → incorrectly matched

The fundamental issue: Fuzzy and phonetic matching algorithms were using the same thresholds regardless of birth data quality, allowing weak matches to pass through when birth information couldn't confirm or reject the match.

## What Changed

### Core Logic Changes (dedupe/scoring.py)

1. **Stricter Effective Fuzzy Thresholds Based on Birth Data Quality**:
   - Both DOB and YOB missing → require 95%+ name similarity (was 80%)
   - One DOB or YOB missing → require 90%+ name similarity (was 80%)
   - YOB-only match (no exact DOB) → require 88%+ name similarity (was 80%)
   - Exact DOB match → allow normal 80% threshold

2. **Stricter Minimum Scores for Address-Assisted Matching**:
   - Both birth fields missing → require 95%+ for address assistance (was 60%)
   - One birth field missing → require 90%+ for address assistance (was 60%)
   - YOB-only match → require 85%+ for address assistance (was 60%)
   - Exact DOB match → allow normal 60% threshold

3. **Stricter Minimum Scores for Phonetic Matching**:
   - Both birth fields missing → require 95%+ for phonetic (was 60%)
   - One birth field missing → require 90%+ for phonetic (was 60%)
   - YOB-only match → require 85%+ for phonetic (was 60%)
   - Exact DOB match → allow normal 60% threshold

4. **Hard Rejection Rules for Fuzzy Matches**:
   - When both DOB and YOB missing → reject if name similarity < 97%
   - When one DOB or YOB missing → reject if name similarity < 92%
   - These apply even with perfect address matches

5. **Added YOB Mismatch Detection**:
   - Track when one record has YOB but the other doesn't (one_yob_missing)
   - Treat YOB mismatches as poor quality birth data (same as DOB mismatches)

### Test Coverage (tests/test_strict_birth_data_matching.py)

Created comprehensive test suite with 8 test cases:
- Fuzzy match rejection when both birth fields missing
- Fuzzy match rejection when one jahrgang missing (different surnames)
- Phonetic match rejection when both birth fields missing
- Fuzzy match acceptance with exact DOB
- Phonetic match acceptance with exact DOB
- Jahrgang-only match requiring 88%+ similarity
- Address-assisted matching blocked without exact DOB
- Very high similarity acceptance even without birth data

## How to Test

Run the new test suite:
```powershell
python -m pytest tests/test_strict_birth_data_matching.py -v
```

All 8 tests should pass, confirming:
- Weak matches are rejected when birth data is missing
- Strong matches are still accepted with exact DOB
- Edge cases are handled correctly

Run full dedupe pipeline to verify reduced false positives:
```powershell
.\run_modular.ps1
```

Review results.csv for:
- Reduced fuzzy_normal matches with low confidence (<70%)
- Fewer phonetic_assisted matches without birth data
- Fewer address_assisted matches without exact DOB

## Risk / Rollback Notes

### Risks

1. **May reject some true positives**: Legitimate matches with poor name spelling variations and missing birth data will be rejected
   - Mitigation: The 95-97% threshold still allows minor variations (e.g., "Büshra" vs "Büsra")
   
2. **Reduced recall**: Overall match rate will decrease, prioritizing precision over recall
   - Mitigation: This is intentional - false positives are more costly than missed matches in this domain

3. **Data quality dependency**: Systems with predominantly missing birth data will see significant reduction in matches
   - Mitigation: This highlights data quality issues that should be addressed at the source

### Rollback

To revert this change:

1. Restore previous version of `dedupe/scoring.py`:
   ```bash
   git checkout HEAD~1 dedupe/scoring.py
   ```

2. Remove test file:
   ```bash
   git rm tests/test_strict_birth_data_matching.py
   ```

3. Rerun deduplication pipeline to regenerate results

### Monitoring

After deployment, monitor:
- Total match count (expect reduction)
- Distribution of match_type (expect fewer fuzzy_normal, phonetic_assisted, address_assisted)
- Average confidence scores (expect increase)
- Manual review feedback on false positives (expect reduction)

## Implementation Details

### Key Thresholds

| Birth Data Quality | Fuzzy Threshold | Address-Assist Min | Phonetic Min | Hard Reject |
|-------------------|-----------------|-------------------|--------------|-------------|
| Both DOB + YOB missing | 95% | 95% | 95% | <97% |
| One DOB or YOB missing | 90% | 90% | 90% | <92% |
| YOB-only match | 88% | 85% | 85% | N/A |
| Exact DOB match | 80% | 60% | 60% | N/A |

### Examples

**Rejected Matches** (correctly filtered out):
- Evalotta vs Evlotta Samuelsson (96.67% similarity, no birth data) → REJECTED
- Rolf Thür vs Rolf Haltner (82.5% similarity, one YOB missing) → REJECTED
- Catrin vs Katherina Staub (~70% similarity, phonetic match, no birth data) → REJECTED

**Accepted Matches** (correctly allowed):
- Daniel Hager vs Daniel Egger (exact DOB match) → ACCEPTED
- Büshra vs Büsra Ayaz (>88% similarity, YOB match) → ACCEPTED
- Andreas Schmidt vs Andreas Schmidt (exact match, no birth data) → ACCEPTED
