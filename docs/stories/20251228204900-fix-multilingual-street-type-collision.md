# Fix Multilingual Street Type Collision in Swisstopo Join

**Date:** 2025-12-28 20:49:00 UTC  
**Type:** Bug Fix  
**Risk:** Medium (changes address normalization logic, requires DB rebuild)

## Summary

Fixed a critical bug in swisstopo address normalization where removing street-type tokens caused collisions between different street types in multilingual Switzerland (e.g., "Augustinergasse" ↔ "Augustinerhof"). Implemented type-preserving join keys with canonicalization to maintain language distinctions while still allowing abbreviation matching.

## Context / Problem

The original swisstopo join used `street_key` (with type tokens removed) for matching. This caused dangerous collisions:

- **German:** "Augustinergasse 8" and "Augustinerhof 8" both normalized to "augustiner" → wrong match
- **French:** "Rue de la Gare" and "Route de la Gare" both normalized to "la gare" → collision risk
- **Italian:** "Via Roma" and "Viale Roma" both normalized to "roma" → ambiguity

The root cause: `normalize_street_key()` removes ALL street-type tokens (`gasse`, `hof`, `rue`, `route`, `via`, `viale`, etc.) to improve fuzzy matching, but this eliminated critical semantic distinctions in a multilingual country.

## What Changed

### 1. Added Type Canonicalization Mapping (`dedupe/preprocess.py`)

Added `_STREET_TYPE_CANONICALIZATION` dict mapping abbreviations to canonical forms:
- **German:** `str` → `strasse`, `gasse` → `gasse`, `hof` → `hof`
- **French:** `av` → `avenue`, `bd` → `boulevard`, `rte` → `route`
- **Italian:** `v` → `via`, `viale` → `viale`

### 2. New Type-Preserving Functions (`dedupe/preprocess.py`)

**`normalize_street_full()`:**
- Splits concatenated names (e.g., "hofstattstrasse" → "hofstatt" + "strasse")
- Canonicalizes type tokens BUT KEEPS THEM
- Returns: `"augustiner gasse"` vs `"augustiner hof"` (distinct!)

**`street_signature_full()`:**
- Same logic but with first-4-char + sort for typo recovery
- Returns: `"augu-gass"` vs `"augu-hof"` (still distinct!)

### 3. Updated DuckDB Index (`scripts/build_swisstopo_index.py`)

Added new columns to `addresses` table:
- `street_full` (type-preserving strict key)
- `street_sig_full` (type-preserving fuzzy key)

Added new indexes:
- `idx_plz4_street_full_house`
- `idx_plz4_street_sig_full_house`

**IMPORTANT:** Existing databases must be rebuilt!

### 4. Updated Join Logic (`dedupe/swisstopo.py`)

Changed matching strategy:
- **Pass A (strict):** Join on `(plz4, street_full, house_num)` ← was `street_key`
- **Pass B (fuzzy):** Join on `(plz4, street_sig_full, house_num)` ← was `street_sig`

Both passes now return `candidate_count` for ambiguity detection.

### 5. Added Ambiguity Guard (`dedupe/preprocess.py`)

Changed overwrite logic:
```python
# OLD: mask = (swis_match_type != "")
# NEW: mask = (swis_match_type != "") & (candidate_count == 1)
```

Only overwrites input addresses when there's a UNIQUE match. If multiple candidates exist, metadata is still filled but address is NOT changed.

### 6. Comprehensive Tests (`tests/test_swisstopo_normalization.py`)

Added test classes:
- `TestMultilingualTypePreservation` (Gasse/Hof, Rue/Route, Via/Viale)
- `TestAmbiguityGuard` (Augustinergasse collision scenario)
- `TestStreetTypeCanonicalization` (abbreviation mappings)

## How to Test

### 1. Unit Tests
```powershell
pytest tests/test_swisstopo_normalization.py::TestMultilingualTypePreservation -v
pytest tests/test_swisstopo_normalization.py::TestAmbiguityGuard -v
```

### 2. Rebuild Swisstopo Database
```powershell
python scripts/build_swisstopo_index.py
```

### 3. Manual Verification
Create test records for Augustinergasse 8 and Augustinerhof 8 in same PLZ → verify they match correctly to different addresses.

## Risk / Rollback Notes

### Risks
1. **Breaking Change:** Existing swisstopo databases are incompatible (missing `street_full` columns)
2. **Match Rate Change:** Slight reduction possible if previously-colliding matches are now blocked
3. **Performance:** Two additional string columns + indexes (minimal impact expected)

### Rollback
If issues arise:
1. Revert commits to restore old `street_key`-based logic
2. Old databases will work with old code
3. No data migration needed (normalization is computed on-the-fly)

### Mitigation
- Type-preserving keys still allow abbreviation matching (`str` ↔ `strasse`)
- Ambiguity guard prevents wrong overwrites even if logic has edge cases
- Metadata fields (`swis_*_ref`) always populated for observability

## Performance Impact

- **DB Size:** +5-10% (two additional indexed string columns)
- **Query Speed:** Negligible (indexed joins, similar cardinality)
- **Preprocessing:** +2-3% (additional normalization functions)

## Examples

### Before (WRONG)
```python
Input: "Augustinergasse 8, 8001 Zürich"
street_key: "augustiner"  # type removed
Matches: BOTH Augustinergasse AND Augustinerhof
Result: ❌ Could normalize to wrong address!
```

### After (CORRECT)
```python
Input: "Augustinergasse 8, 8001 Zürich"
street_full: "augustiner gasse"  # type preserved
Matches: ONLY Augustinergasse
candidate_count: 1
Result: ✅ Correct unique match
```

### Abbreviation Still Works
```python
Input: "Hauptstr 10"  
street_full: "haupt strasse"  # "str" → "strasse"
DB:    "Hauptstrasse 10"
street_full: "haupt strasse"
Result: ✅ Match (canonicalization works)
```

## Dependencies

- No new external dependencies
- Requires DuckDB rebuild (one-time operation)
- Compatible with all existing deduplication logic (blocking unchanged)

## Related Issues

- Fixes: Augustinergasse ↔ Augustinerhof collision bug
- Related: PLZ6 handling (already implemented)
- Related: Concatenated street name splitting (already implemented)

## Follow-up

- Monitor match rates after deployment
- Consider adding more language-specific canonicalization rules if needed
- Consider logging ambiguous matches (candidate_count > 1) for analysis
