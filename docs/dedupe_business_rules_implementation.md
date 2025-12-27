# Dedupe Module Business Rules Implementation

**Date:** 27. December 2025  
**Version:** 2.0  
**Status:** ✅ Aligned with duplicate_checker_optimized.py

---

## Overview

This document describes the implementation of business rules in the `dedupe/` module to align it with the established business rules in `duplicate_checker_optimized.py`.

## Changes Summary

### 1. German Umlaut Normalization (`dedupe/preprocess.py`)

**Status:** ✅ Implemented

**Change:** Added explicit German umlaut normalization BEFORE unidecode processing.

```python
# German umlaut normalization BEFORE unidecode
s = s.str.replace('ß', 'ss', regex=False)
s = s.str.replace('ü', 'ue', regex=False)
s = s.str.replace('ä', 'ae', regex=False)
s = s.str.replace('ö', 'oe', regex=False)
```

**Rationale:** Ensures "Müller" and "Mueller" normalize to the same value ("mueller"), critical for exact matching.

**Examples:**
- "Müller" → "mueller"
- "Mueller" → "mueller"
- "Größer" → "groesser"
- "Groesser" → "groesser"

---

### 2. Name2/Zweitname Rule (`dedupe/scoring.py`)

**Status:** ✅ Implemented

**Change:** Added `check_zweitname()` function with compound surname support.

**Business Logic:**

1. **Both Name2 fields populated:** Must match exactly
   - Example: Name2_A="Maria", Name2_B="Maria" → ✅ Pass

2. **Both Name2 fields empty:** Automatically pass
   - Example: Name2_A="", Name2_B="" → ✅ Pass

3. **One Name2 populated, one empty:** Check if suffix match
   - Example: Name="Rohner-Stassek", Name2="" vs Name="Rohner", Name2="-Stassek" → ✅ Pass

**Impact:** Prevents false positives from different compound surnames or middle names.

---

### 3. Name Swapping Detection (`dedupe/scoring.py`)

**Status:** ✅ Implemented

**Change:** Added `compare_names_with_swap()` function that compares both normal and swapped name orders.

**Business Logic:**

```python
# Normal comparison
normal_score = (vorname_similarity + name_similarity) / 2

# Swapped comparison  
swapped_score = (vorname_vs_name_similarity + name_vs_vorname_similarity) / 2

# Use best score, flag if swapped
is_swapped = swapped_score > normal_score
```

**Examples:**
- Normal: Vorname="Max", Name="Müller" vs Vorname="Max", Name="Mueller" → exact_normal
- Swapped: Vorname="Anna", Name="Schmidt" vs Vorname="Schmidt", Name="Anna" → exact_swapped

**Impact:** Identifies potential fraud indicators (intentional name swapping).

---

### 4. Two-Stage Architecture (`dedupe/scoring.py`)

**Status:** ✅ Implemented

**Change:** Implemented distinct handling for exact matches vs fuzzy matches.

**Stage 1: Exact Matching**
- Check if normalized names match exactly (normal or swapped order)
- Confidence: 85-100%
- Match types: `exact_normal`, `exact_swapped`

**Stage 2: Fuzzy Matching**
- Only if not exact match
- Use fuzzy string similarity
- Confidence: 65-95% (capped to not exceed exact matches)
- Match types: `fuzzy_normal`, `fuzzy_swapped`

**Benefits:**
- Clearer confidence scoring
- Explicit fraud detection (swapped names)
- More accurate match classification

---

### 5. Match Type Classification (`dedupe/scoring.py`)

**Status:** ✅ Implemented

**Change:** Enhanced `MatchResult` dataclass with `is_swapped` field and detailed `reason` values.

**Match Types:**

| Match Type | Confidence Range | Description |
|------------|-----------------|-------------|
| `exact_normal` | 90-100% | Exact name match in normal order |
| `exact_swapped` | 85-95% | Exact name match in swapped order (⚠️ suspicious) |
| `fuzzy_normal` | 70-90% | Fuzzy name match in normal order |
| `fuzzy_swapped` | 65-85% | Fuzzy name match in swapped order (⚠️ suspicious) |

**Usage:**
```python
result = score_pair(i, j, cols)
if result:
    if result.is_swapped:
        print(f"⚠️ Suspicious: {result.reason}")
```

---

### 6. Enhanced Candidate Generation (`dedupe/candidates.py`)

**Status:** ✅ Implemented

**Change:** Modified `iter_exact_pairs()` to check both normal and swapped name orders.

**Implementation:**
- Hash records with normal name order (Vorname, Name)
- Hash records with swapped name order (Name, Vorname)
- Generate pairs from both hash groups
- Deduplicate pairs to avoid double-counting

**Impact:** Ensures all exact matches (normal and swapped) are detected in Stage 1.

---

## Confidence Scoring Formulas

### Exact Matches

**Exact Normal:**
```
confidence = 90 + (address_match_ratio × 10)
Range: 90-100%
```

**Exact Swapped:**
```
confidence = 85 + (address_match_ratio × 10)
Range: 85-95%
```

### Fuzzy Matches

**Fuzzy Normal:**
```
base = name_similarity × 50
address_bonus = address_match_ratio × 30
confidence = base + address_bonus
Max: 95% (capped)
Range: 70-95%
```

**Fuzzy Swapped:**
```
base = name_similarity × 50
address_bonus = address_match_ratio × 30
swap_penalty = 5
confidence = base + address_bonus - swap_penalty
Max: 95% (capped)
Range: 65-90%
```

---

## Business Rules Checklist

| Rule | Status | Implementation |
|------|--------|----------------|
| ✅ Date Rule (Year equality) | Implemented | `scoring.py` line 84-88 |
| ✅ Name2/Zweitname Rule | Implemented | `scoring.py` line 89-96 |
| ✅ German Umlaut Normalization | Implemented | `preprocess.py` line 14-21 |
| ✅ Name Swapping Detection | Implemented | `scoring.py` line 55-76 |
| ✅ Two-Stage Architecture | Implemented | `scoring.py` line 136-163 |
| ✅ Match Type Classification | Implemented | `scoring.py` throughout |
| ✅ Exact Match Pairs (Normal + Swapped) | Implemented | `candidates.py` line 26-62 |
| ❌ Phonetic Matching (Cologne Phonetic) | Not Implemented | Optional enhancement |
| ❌ Address-Assisted Matching (60-70% range) | Not Implemented | Optional enhancement |
| ❌ Multi-Pass Blocking | Not Implemented | Optional enhancement |

---

## Compatibility with duplicate_checker_optimized.py

### ✅ Fully Compatible:
1. Date rule (year equality check)
2. Name2/Zweitname rule (compound surname support)
3. German umlaut normalization (ü→ue, ä→ae, ö→oe, ß→ss)
4. Name swapping detection (normal vs swapped comparison)
5. Two-stage architecture (exact then fuzzy)
6. Match type classification (exact_normal, exact_swapped, fuzzy_normal, fuzzy_swapped)

### ⚠️ Not Implemented (Optional):
1. **Phonetic Matching:** Cologne Phonetic fallback for 60-70% similarity range
2. **Address-Assisted Matching:** Strong address + borderline name score
3. **Multi-Pass Blocking:** Secondary phonetic blocking pass

These features can be added in future enhancements if needed.

---

## Testing

### Recommended Test Cases

1. **German Umlaut Test:**
   - Input: "Müller" vs "Mueller"
   - Expected: exact_normal match

2. **Name2 Rule Test:**
   - Input: Name="Rohner-Stassek", Name2="" vs Name="Rohner", Name2="-Stassek"
   - Expected: Pass Name2 rule

3. **Name Swapping Test:**
   - Input: Vorname="Anna", Name="Schmidt" vs Vorname="Schmidt", Name="Anna"
   - Expected: exact_swapped match with is_swapped=True

4. **Date Rule Test:**
   - Input: Year=1980 vs Year=1985
   - Expected: No match (rejected)

5. **Two-Stage Architecture Test:**
   - Exact: "Max Müller" vs "Max Mueller" → exact_normal (90-100%)
   - Fuzzy: "Max Muller" vs "Mux Mueller" → fuzzy_normal (70-90%)

---

## Performance Impact

**Estimated Impact:** +5-10% processing time

**Breakdown:**
- German umlaut normalization: +1-2% (one-time preprocessing)
- Name2 rule check: +1-2% (simple string comparison)
- Name swapping detection: +2-4% (double fuzzy comparison)
- Two-stage architecture: +1-2% (exact match check before fuzzy)

**Benefit:** More accurate matching, better fraud detection, clearer confidence scores

---

## Migration Notes

### For Existing Code

If you're already using the `dedupe/` module, these changes are **backward compatible** with one exception:

**Breaking Change:** `MatchResult` dataclass now includes `is_swapped` field.

**Migration:**
```python
# Old code (still works with default value)
result = MatchResult(i=0, j=1, score=95.0, name_score=100.0, addr_score=80.0, reason="exact")

# New code (recommended)
result = MatchResult(i=0, j=1, score=95.0, name_score=100.0, addr_score=80.0, 
                     reason="exact_normal", is_swapped=False)
```

### Configuration

No configuration changes required. The business rules are always active.

---

## Future Enhancements

### Priority 1: Phonetic Matching
- Implement Cologne Phonetic for German names
- Fallback for 60-70% similarity range
- Estimated effort: 2-3 hours

### Priority 2: Address-Assisted Matching
- Strong address match + borderline name score
- Confidence boost mechanism
- Estimated effort: 1-2 hours

### Priority 3: Multi-Pass Blocking
- Secondary phonetic blocking pass
- Year-based sub-blocking
- Estimated effort: 3-4 hours

---

## References

- **Source:** `duplicate_checker_optimized.py`
- **Documentation:** `docs/businessrules.md`
- **Implementation:** `dedupe/scoring.py`, `dedupe/preprocess.py`, `dedupe/candidates.py`

---

## Changelog

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-12-27 | 2.0 | Aligned dedupe/ module with duplicate_checker_optimized.py business rules | System |
| 2025-12-27 | 2.0 | Added German umlaut normalization | System |
| 2025-12-27 | 2.0 | Implemented Name2/Zweitname rule | System |
| 2025-12-27 | 2.0 | Added name swapping detection | System |
| 2025-12-27 | 2.0 | Implemented two-stage architecture | System |
| 2025-12-27 | 2.0 | Enhanced match type classification | System |

---

**Status:** ✅ Implementation Complete  
**Business Rules Alignment:** 100% (core rules)  
**Optional Enhancements:** 0% (phonetic, address-assisted, multi-pass)
