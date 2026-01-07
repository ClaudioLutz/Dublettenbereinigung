# Business Rules & Logic

This document describes the business rules, matching logic, and blocking strategies implemented in the Swiss Person Deduplication pipeline.

## Overview

The system identifies duplicate person records using a two-stage architecture:
1.  **Blocking**: Efficiently groups potential duplicates into blocks (candidates).
2.  **Matching (Scoring)**: Detailed comparison of candidates within blocks using business rules to assign confidence scores and match types.

## 1. Blocking Strategy

The system supports two blocking modes, with **Address-Based Blocking** being the default.

### Address-Based Blocking (Default)
Finds duplicates within the same building/address. Ideal for high-quality address data.

*   **Primary Pass (Building Level)**: Groups records by `PLZ` + `Street Key` (normalized) + `House Number` (numeric part).
*   **Secondary Pass (Typo Recovery)**: Groups records by `PLZ` + `House Number` (numeric part) + `Street Signature` (typo-robust).
*   **Candidate Generation**: Uses **Sorted Neighborhood Method** with a sliding window (default size: 10).
    *   Sorts records within a block by Name (e.g., `Last|First` and `First|Last`).
    *   Compares each record with its nearest neighbors.
    *   Apply a lightweight name similarity pre-filter (default: 88%) to discard obvious non-matches early.

### Name-Based Blocking (Legacy)
Finds duplicates across different addresses based on name similarity.

*   **Primary Pass**: Groups by `Last Name` (prefix) + `First Name` (prefix) + `PLZ` + `Year`.
*   **Secondary Pass**: Uses a swap-invariant key (sorted prefixes of names).
*   **Candidate Generation**: Uses **Exact Pairs** (hash collision) or `process.extract` for fuzzy candidates.

## 2. Matching Logic (Scoring)

Pairs identified by blocking are scored in `dedupe/scoring.py`. The process involves hard gates, exact matching, and fuzzy matching with strict penalties.

### 2.1 Hard Gates (Rejection Rules)
Pairs are immediately rejected (score = 0) if:
*   **DOB Mismatch**: Both records have a full Date of Birth (YYYYMMDD), and they differ.
*   **YOB Mismatch**: Both records have a Year of Birth (from DOB or separate field), and they differ.
*   **Different Buildings**: Both records have a parsed house number, and the numeric parts differ (e.g., "12" vs "14").

### 2.2 Soft Gates (Confidence Penalties)
Pairs receive confidence penalties (but are not rejected) if:
*   **Gender Mismatch**: Both records have known genders (from Pa_S_Anrede field), genders differ, both at same address (PLZ + house number match), and name similarity ≥75%.
    *   **Penalty**: -20 points (pushes below auto-merge threshold)
    *   **Purpose**: Prevents false positives for siblings/spouses with similar names (e.g., "Peter" vs "Petra", "Andreas" vs "Andrea")
    *   **Gender Mapping**: Herr/Mr/Monsieur/Signor → M, Frau/Mrs/Ms/Miss/Madame/Signora → F, Unknown/Missing → U
    *   **Match Types Affected**: All match types receive `_different_gender` suffix when penalty applies

### 2.3 Stage 1: Exact Matching
Checks for exact string equality on normalized names.

*   **Exact Normal**: `First A == First B` AND `Last A == Last B`.
    *   Confidence: **95-100%** (depends on address match quality).
*   **Exact Swapped**: `First A == Last B` AND `Last A == First B`.
    *   Confidence: **90-100%** (depends on address match quality).

**Address Validation for Exact Matches:**
*   Must not have conflicting PLZs.
*   Must not have conflicting house numbers.
*   Must have decent street similarity (>70%).

### 2.4 Stage 2: Fuzzy Matching
If not an exact match, fuzzy string similarity (Rapidfuzz WRatio) is calculated.

*   **Name2/Zweitname Rule**: If `Name2` is present, it is checked.
    *   If both have `Name2`, they must match.
    *   If one has `Name2`, it's checked as a suffix of the other's surname (compound name support).
    *   Unmatched `Name2` prevents a match.
*   **Name Swapping**: Both "Normal" (`First A` vs `First B`) and "Swapped" (`First A` vs `Last B`) orientations are scored. The better orientation is used.

#### Strict Fuzzy Rules
Fuzzy matches (names not identical) require stronger evidence to be accepted:

1.  **Missing Birth Data**:
    *   If **BOTH** DOB and YOB are missing: Requires **97%** name similarity.
    *   If **ONE** is missing: Requires **92%** name similarity.
2.  **Address Requirements**:
    *   If **NO Exact DOB Match**: Requires **Exact Address Match** (Same PLZ, Same House Number, Street similarity >90%).
    *   If **Exact DOB Match**: Allows slightly lower address similarity (>50%), but strictly rejects PLZ/House mismatches.

#### Advanced Matching Features

*   **Address-Assisted Matching**:
    *   For borderline name matches (60-80% similarity).
    *   If the address match is very strong (PLZ match + Street match), the pair can be accepted.
    *   *Constraint*: Only allowed if birth data is present and consistent (not allowed if DOB/YOB are missing).
    *   Result: `address_assisted_normal` / `address_assisted_swapped` (Confidence: 68-80%).

*   **Phonetic Matching**:
    *   Uses **Cologne Phonetics** (Kölner Phonetik).
    *   For borderline name matches (60-80% similarity).
    *   If phonetic codes match exactly, the pair can be accepted.
    *   *Constraint*: Strictly gated by birth data availability (e.g., requires 95% similarity if DOB missing).
    *   Result: `phonetic_assisted_normal` / `phonetic_assisted_swapped` (Confidence: 70-82%).

*   **First Word Bonus**:
    *   If the first token of the First Name matches exactly (e.g., "Jean-Pierre" vs "Jean"), a small score bonus (5-10%) is applied.

## 3. Data Normalization

Raw data is preprocessed in `dedupe/preprocess.py` to ensure consistent comparison.

### Names
*   **German Umlauts**: Converted **before** unicode normalization (e.g., `ü` -> `ue`, `ß` -> `ss`).
*   **Case/Whitespace**: Lowercased, stripped, multiple spaces collapsed.
*   **Unidecode**: Accents removed (e.g., `é` -> `e`).

### Addresses
*   **Street Keys**:
    *   Common tokens removed (`strasse`, `weg`, `rue`, `via`, etc.).
    *   Concatenated suffixes split (e.g., "Bahnhofstrasse" -> "bahnhof" + "strasse").
*   **Street Signature**:
    *   First 4 characters of each token, sorted alphabetically, joined by `-`.
    *   Example: "Bahnhofstrasse" -> "bahn".
*   **House Numbers**:
    *   Parsed into `Numeric Core` + `Suffix`.
    *   Comparison uses only the numeric core (e.g., "12A" matches "12").
*   **PLZ**:
    *   Reduced to 4 digits (Swiss standard).

### Dates
*   **DOB**: Parsed to integer `YYYYMMDD` (or -1 if invalid).
*   **YOB**: Extracted from `Jahrgang` column or DOB year.

## 4. Match Types & Confidence

The system assigns a `match_type` (reason) and a confidence score (0-100) to each pair.

| Match Type | Confidence Range | Description |
| :--- | :--- | :--- |
| `exact_normal` | 90-100% | Exact name match (First=First, Last=Last). Score depends on address match. |
| `exact_swapped` | 85-100% | Exact name match (First=Last, Last=First). |
| `fuzzy_normal` | 40-95% | Fuzzy name match. Score = Base Name Score + Address Bonus - DOB Penalty. |
| `fuzzy_swapped` | 40-95% | Fuzzy name match (swapped). Penalized slightly (-5%). |
| `address_assisted_normal` | 70-80% | Borderline name match salvaged by strong address match. |
| `address_assisted_swapped` | 68-78% | Borderline swapped name match salvaged by strong address match. |
| `phonetic_assisted_normal` | 72-82% | Borderline name match salvaged by identical phonetic code. |
| `phonetic_assisted_swapped` | 70-80% | Borderline swapped name match salvaged by identical phonetic code. |

## 5. Configuration

Key parameters in `dedupe/pipeline.py` and `dedupe/blocking.py`:

*   `blocking_mode`: `address` (default) or `name`.
*   `fuzzy_threshold`: Base threshold for fuzzy matching (default: 0.80).
*   `window_size`: Sliding window size for address blocking (default: 10).
*   `enable_address_aware`: Toggle for address-assisted matching (default: True).
