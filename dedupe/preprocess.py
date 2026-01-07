from __future__ import annotations

import re
import pandas as pd
import numpy as np
from unidecode import unidecode

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")

# Swiss multilingual street type tokens to normalize/remove (for blocking only)
_STREET_TYPES = {
    # German
    'str', 'strasse', 'strasse', 'gasse', 'weg', 'platz', 'allee', 'ring', 'hof',
    # French
    'rue', 'av', 'avenue', 'chemin', 'route', 'place', 'cours', 'boulevard', 'bd',
    # Italian
    'via', 'viale', 'piazza', 'corso', 'largo',
    # Common abbreviations
    'st', 'ave', 'rd', 'pl', 'blvd'
}

# Canonical type token mapping: abbreviation → canonical form
# This preserves type distinction while normalizing abbreviations
_STREET_TYPE_CANONICALIZATION = {
    # German
    'str': 'strasse',
    'strasse': 'strasse',
    'gasse': 'gasse',
    'weg': 'weg',
    'platz': 'platz',
    'allee': 'allee',
    'ring': 'ring',
    'hof': 'hof',
    # French
    'rue': 'rue',
    'av': 'avenue',
    'avenue': 'avenue',
    'ch': 'chemin',
    'chemin': 'chemin',
    'rte': 'route',
    'route': 'route',
    'pl': 'place',
    'place': 'place',
    'cours': 'cours',
    'bd': 'boulevard',
    'blvd': 'boulevard',
    'boulevard': 'boulevard',
    # Italian
    'v': 'via',
    'via': 'via',
    'viale': 'viale',
    'piazza': 'piazza',
    'corso': 'corso',
    'largo': 'largo',
}

# Street type suffixes for splitting concatenated street names (e.g., "Hofstattstrasse" -> "hofstatt" + "strasse")
_STREET_SUFFIXES = [
    'strasse', 'gasse', 'weg', 'platz', 'allee', 'ring', 'hof',
    'avenue', 'chemin', 'route', 'place', 'cours', 'boulevard',
    'viale', 'piazza', 'corso', 'largo'
]


def _split_street_suffix(token: str) -> list[str]:
    """
    Split concatenated street names like 'hofstattstrasse' into ['hofstatt', 'strasse'].

    Args:
        token: A single normalized street token

    Returns:
        List of split tokens (may be just [token] if no suffix found)
    """
    if len(token) <= 4:
        return [token]

    # Try each suffix (sorted by length descending to match longest first)
    for suffix in sorted(_STREET_SUFFIXES, key=len, reverse=True):
        if token.endswith(suffix) and len(token) > len(suffix):
            # Split into root + suffix
            root = token[:-len(suffix)]
            if len(root) >= 2:  # Ensure root is meaningful
                return [root, suffix]

    return [token]


def _norm_series(s: pd.Series) -> pd.Series:
    s = s.astype("string")
    s = s.fillna("")
    s = s.str.strip().str.lower()

    # German umlaut normalization BEFORE unidecode
    # This ensures "Müller" and "Mueller" both normalize to "mueller"
    s = s.str.replace('ß', 'ss', regex=False)
    s = s.str.replace('ü', 'ue', regex=False)
    s = s.str.replace('ä', 'ae', regex=False)
    s = s.str.replace('ö', 'oe', regex=False)

    s = s.map(unidecode)
    s = s.str.replace(_NON_ALNUM, " ", regex=True)
    s = s.str.replace(_WS, " ", regex=True).str.strip()
    return s


def normalize_street_key(street: pd.Series) -> pd.Series:
    """
    Normalize street names for strict blocking by removing street type tokens.
    Handles concatenated street names like "Hofstattstrasse" by splitting them first.

    Args:
        street: Already normalized street series

    Returns:
        Street key with type tokens removed and tokens collapsed
    """
    def _process_street(s: str) -> str:
        if not s:
            return ""

        # Split into tokens
        tokens = s.split()

        # Split concatenated street names (e.g., "hofstattstrasse" -> ["hofstatt", "strasse"])
        expanded_tokens = []
        for token in tokens:
            expanded_tokens.extend(_split_street_suffix(token))

        # Remove street type tokens
        filtered = [t for t in expanded_tokens if t not in _STREET_TYPES]

        # Join remaining tokens
        return " ".join(filtered)

    return street.map(_process_street).astype("string")


def street_signature(street: pd.Series) -> pd.Series:
    """
    Create a street signature robust to minor typos for typo recovery.
    Handles concatenated street names like "Hofstattstrasse" by splitting them first.

    Strategy:
    - Split concatenated street names (e.g., "hofstattstrasse" -> ["hofstatt", "strasse"])
    - Remove street type tokens
    - Keep first 4 characters of each remaining token
    - Sort tokens alphabetically
    - Join with "-"

    Args:
        street: Already normalized street series

    Returns:
        Street signature series
    """
    def _process_street(s: str) -> str:
        if not s:
            return ""

        # Split into tokens
        tokens = s.split()

        # Split concatenated street names (e.g., "hofstattstrasse" -> ["hofstatt", "strasse"])
        expanded_tokens = []
        for token in tokens:
            expanded_tokens.extend(_split_street_suffix(token))

        # Remove street type tokens
        filtered = [t for t in expanded_tokens if t not in _STREET_TYPES]

        # Keep first 4 chars of each token
        prefixed = [t[:4] for t in filtered if t]

        # Sort tokens
        prefixed.sort()

        # Join with "-"
        return "-".join(prefixed)

    return street.map(_process_street).astype("string")


def normalize_street_full(street: pd.Series) -> pd.Series:
    """
    Normalize street names for type-preserving swisstopo joins (multilingual safe).
    
    This function preserves street type tokens (Gasse vs Hof, Rue vs Route, Via vs Viale)
    while canonicalizing abbreviations within each language.
    
    Strategy:
    - Split concatenated street names (e.g., "hofstattstrasse" -> ["hofstatt", "strasse"])
    - Canonicalize type tokens (e.g., "str" → "strasse", "av" → "avenue", "v" → "via")
    - Keep all tokens (including canonicalized type tokens)
    - Join tokens back
    
    This prevents collisions like:
    - "Augustinergasse" ≠ "Augustinerhof"
    - "Zähringer Platz" ≠ "Zähringer Strasse"
    - "Rue ..." ≠ "Route ..."
    
    Args:
        street: Already normalized street series
        
    Returns:
        Type-preserving street key with canonicalized type tokens
    """
    def _process_street(s: str) -> str:
        if not s:
            return ""
        
        # Split into tokens
        tokens = s.split()
        
        # Split concatenated street names (e.g., "hofstattstrasse" -> ["hofstatt", "strasse"])
        expanded_tokens = []
        for token in tokens:
            expanded_tokens.extend(_split_street_suffix(token))
        
        # Canonicalize type tokens (but keep them!)
        canonicalized = []
        for token in expanded_tokens:
            canonical = _STREET_TYPE_CANONICALIZATION.get(token, token)
            canonicalized.append(canonical)
        
        # Join all tokens (including type tokens)
        return " ".join(canonicalized)
    
    return street.map(_process_street).astype("string")


def street_signature_full(street: pd.Series) -> pd.Series:
    """
    Create a type-preserving street signature for typo recovery (multilingual safe).
    
    Similar to street_signature() but preserves type tokens after canonicalization.
    This allows fuzzy matching while preventing cross-type collisions.
    
    Strategy:
    - Split concatenated street names (e.g., "hofstattstrasse" -> ["hofstatt", "strasse"])
    - Canonicalize type tokens (e.g., "str" → "strasse", "av" → "avenue")
    - Keep all tokens (including canonicalized type tokens)
    - Keep first 4 characters of each token
    - Sort tokens alphabetically
    - Join with "-"
    
    Args:
        street: Already normalized street series
        
    Returns:
        Type-preserving street signature
    """
    def _process_street(s: str) -> str:
        if not s:
            return ""
        
        # Split into tokens
        tokens = s.split()
        
        # Split concatenated street names (e.g., "hofstattstrasse" -> ["hofstatt", "strasse"])
        expanded_tokens = []
        for token in tokens:
            expanded_tokens.extend(_split_street_suffix(token))
        
        # Canonicalize type tokens (but keep them!)
        canonicalized = []
        for token in expanded_tokens:
            canonical = _STREET_TYPE_CANONICALIZATION.get(token, token)
            canonicalized.append(canonical)
        
        # Keep first 4 chars of each token
        prefixed = [t[:4] for t in canonicalized if t]
        
        # Sort tokens
        prefixed.sort()
        
        # Join with "-"
        return "-".join(prefixed)
    
    return street.map(_process_street).astype("string")


def extract_plz4(plz: pd.Series) -> pd.Series:
    """
    Extract 4-digit PLZ from potentially 6-digit postcode.

    Swiss postcodes are 4 digits, but some systems use 6-digit codes (PLZ6).
    This function extracts the first 4 digits for matching with swisstopo data.

    Examples:
    - "965800" -> "9658"
    - "900000" -> "9000"
    - "8000" -> "8000"
    - "" -> ""

    Args:
        plz: Postcode series (already normalized)

    Returns:
        4-digit postcode series
    """
    def _extract(p: str) -> str:
        if not p:
            return ""
        # Extract first 4 digits
        digits = "".join(c for c in p if c.isdigit())
        return digits[:4] if len(digits) >= 4 else digits

    return plz.map(_extract).astype("string")


def parse_house_number(house: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Parse house number into numeric core and suffix.

    Examples:
    - "12" -> (12, "")
    - "12A" -> (12, "a")
    - "12a" -> (12, "a")
    - "12b" -> (12, "b")

    Args:
        house: House number series (already normalized to lowercase)

    Returns:
        Tuple of (house_num, house_sfx) where:
        - house_num: numeric part as string ("" if no numeric part)
        - house_sfx: alphabetic suffix as lowercase string ("" if no suffix)
    """
    def _parse(h: str) -> tuple[str, str]:
        if not h:
            return ("", "")

        # Extract leading digits
        numeric = ""
        suffix = ""

        for i, ch in enumerate(h):
            if ch.isdigit():
                numeric += ch
            else:
                # Rest is suffix (letters only, lowercase)
                suffix = "".join(c.lower() for c in h[i:] if c.isalpha())
                break

        return (numeric, suffix)

    parsed = house.map(_parse)
    house_num = parsed.map(lambda x: x[0]).astype("string")
    house_sfx = parsed.map(lambda x: x[1]).astype("string")

    return house_num, house_sfx


def parse_dob_ymd(date_series: pd.Series) -> pd.Series:
    """
    Parse date of birth into YYYYMMDD integer format.

    Args:
        date_series: Date series (can be datetime or string)

    Returns:
        Series of integers in YYYYMMDD format, -1 for missing/unparseable dates
    """
    dt = pd.to_datetime(date_series, errors="coerce")

    # Convert to YYYYMMDD integer
    valid_mask = dt.notna()
    result = pd.Series(-1, index=dt.index, dtype=np.int32)

    if valid_mask.any():
        year = dt.dt.year.fillna(0).astype(np.int32)
        month = dt.dt.month.fillna(0).astype(np.int32)
        day = dt.dt.day.fillna(0).astype(np.int32)
        ymd_values = (year[valid_mask] * 10000 + month[valid_mask] * 100 + day[valid_mask]).astype(np.int32)
        result.loc[valid_mask] = ymd_values

    return result


def extract_yob(dob_ymd: pd.Series, jahrgang: pd.Series) -> pd.Series:
    """
    Extract year of birth from either Jahrgang or DOB.

    Priority:
    1. If Jahrgang is present and valid -> use it
    2. Else if dob_ymd is present -> extract YYYY from it
    3. Else -> -1

    Args:
        dob_ymd: DOB in YYYYMMDD format (-1 if missing)
        jahrgang: Jahrgang column (year of birth, may be missing)

    Returns:
        Series of year of birth as int32, -1 for missing
    """
    # Try to parse Jahrgang
    jahrgang_series = pd.to_numeric(jahrgang, errors="coerce")

    # Initialize with -1
    yob = pd.Series(-1, index=dob_ymd.index, dtype=np.int32)

    # Use Jahrgang if valid
    valid_jahrgang = jahrgang_series.notna() & (jahrgang_series > 1900) & (jahrgang_series < 2100)
    yob[valid_jahrgang] = jahrgang_series[valid_jahrgang].astype(np.int32)

    # Fall back to DOB year if Jahrgang not available
    missing_yob = yob == -1
    valid_dob = (dob_ymd != -1) & missing_yob
    yob[valid_dob] = (dob_ymd[valid_dob] // 10000).astype(np.int32)

    return yob


def preprocess(df: pd.DataFrame, *, address_normalizer=None) -> dict[str, object]:
    """
    Preprocess dataframe with address-based blocking support.

    Args:
        df: Input dataframe with raw address fields
        address_normalizer: Optional SwisstopoAddressNormalizer for reference-based normalization

    Returns dict with:
    - Original fields: first, last, name2, street, plz, house, ort, full_name
    - Address blocking fields: street_key, street_sig, house_num, house_sfx
    - Address keys: addr_key_building, addr_key_typo
    - Date fields: dob_ymd, yob, year (legacy)
    """
    out: dict[str, object] = {}
    n = len(df)

    # Name fields
    first = _norm_series(df["Vorname"])
    last = _norm_series(df["Name"])
    name2 = _norm_series(df.get("Name2", pd.Series([""] * n)))

    # Gender field (Pa_S_Anrede: Herr/Frau/etc)
    # Normalize to simple M/F/U (male/female/unknown) for comparison
    gender_raw = df.get("Pa_S_Anrede", pd.Series([""] * n)).astype("string").fillna("").str.strip().str.lower()
    gender = gender_raw.replace({
        'herr': 'M',
        'frau': 'F',
        'mr': 'M',
        'mrs': 'F',
        'ms': 'F',
        'miss': 'F',
        'monsieur': 'M',
        'madame': 'F',
        'signor': 'M',
        'signora': 'F',
    }).replace('', 'U')  # U = Unknown

    # Address fields - basic normalization
    street = _norm_series(df.get("Strasse", pd.Series([""] * n)))
    plz = _norm_series(df.get("Plz", pd.Series([""] * n)))
    house = _norm_series(df.get("HausNummer", pd.Series([""] * n)))
    ort = _norm_series(df.get("Ort", pd.Series([""] * n)))

    # Address-specific fields for blocking (initial computation)
    street_key = normalize_street_key(street)
    street_sig = street_signature(street)
    house_num, house_sfx = parse_house_number(house)

    # Initialize PLZ4 extraction once (needed for both normalization and blocking)
    # Extract 4-digit PLZ for matching with swisstopo (which uses 4-digit postcodes)
    plz4_used = extract_plz4(plz)

    # Initialize swisstopo output fields (empty by default)
    # Use df.index to ensure alignment with input dataframe
    idx_all = df.index
    swis_match_type = pd.Series("", index=idx_all, dtype="string")
    swis_adr_egaid_ref = pd.Series("", index=idx_all, dtype="string")
    swis_bdg_egid_ref = pd.Series("", index=idx_all, dtype="string")
    swis_changed = pd.Series(False, index=idx_all, dtype="bool")

    # Store raw reference strings
    swis_street_label_ref = pd.Series("", index=idx_all, dtype="string")
    swis_adr_number_ref = pd.Series("", index=idx_all, dtype="string")
    swis_plz4_ref = pd.Series("", index=idx_all, dtype="string")
    swis_ort_ref = pd.Series("", index=idx_all, dtype="string")

    # Swisstopo-based address normalization (if enabled)
    if address_normalizer is not None:
        # Compute type-preserving keys for swisstopo joins (multilingual safe)
        street_full = normalize_street_full(street)
        street_sig_full = street_signature_full(street)
        
        # Build keys DataFrame for normalizer
        # We pass range(n) as row_id to the normalizer to get 0-based indices back
        keys_df = pd.DataFrame({
            'row_id': range(n),
            'plz4': plz4_used.values,  # Use values to ignore index mismatch
            'street_key': street_key.values,  # For blocking (legacy)
            'street_sig': street_sig.values,  # For blocking (legacy)
            'street_full': street_full.values,  # Type-preserving strict key
            'street_sig_full': street_sig_full.values,  # Type-preserving fuzzy key
            'house_num': house_num.values,
        })

        # Get reference matches from swisstopo
        ref_matches = address_normalizer.normalize_chunk(keys_df)

        if not ref_matches.empty:
            # Map the returned 0-based row_id back to the actual df index
            matched_row_ids = ref_matches["row_id"].values
            target_indices = df.index[matched_row_ids]

            # Create a dataframe with the target index for easier assignment
            ref_indexed = ref_matches.set_index(target_indices)

            # Fill metadata fields (always fill these for observability)
            swis_match_type.loc[ref_indexed.index] = ref_indexed["match_type"].astype("string")
            swis_adr_egaid_ref.loc[ref_indexed.index] = ref_indexed["adr_egaid_ref"].astype("string")
            swis_bdg_egid_ref.loc[ref_indexed.index] = ref_indexed["bdg_egid_ref"].astype("string")

            swis_street_label_ref.loc[ref_indexed.index] = ref_indexed["street_label_ref"].astype("string")
            swis_adr_number_ref.loc[ref_indexed.index] = ref_indexed["adr_number_ref"].astype("string")
            swis_plz4_ref.loc[ref_indexed.index] = ref_indexed["plz4_ref"].astype("string")
            swis_ort_ref.loc[ref_indexed.index] = ref_indexed["ort_ref"].astype("string")

            # Normalize reference strings in one go
            ref_street = _norm_series(swis_street_label_ref)
            ref_house = _norm_series(swis_adr_number_ref)
            ref_ort = _norm_series(swis_ort_ref)
            ref_plz4 = swis_plz4_ref.copy()

            # AMBIGUITY GUARD: Only overwrite when we have a unique match (candidate_count == 1)
            # This prevents "Augustinergasse 8" from being overwritten to "Augustinerhof 8"
            candidate_count = pd.Series(0, index=idx_all, dtype="int32")
            candidate_count.loc[ref_indexed.index] = ref_indexed["candidate_count"].astype("int32")
            
            # Create mask: has match AND unique (not ambiguous)
            mask = (swis_match_type != "") & (candidate_count == 1)

            # Store values before change to detect changes
            street_before = street.copy()
            house_before = house.copy()
            plz4_before = plz4_used.copy()
            ort_before = ort.copy()

            # Apply normalization where we have matches
            street = street.where(~mask, ref_street)
            house = house.where(~mask, ref_house)
            ort = ort.where(~mask, ref_ort)

            # IMPORTANT: keep plz as original raw-normalized for legacy display, but use plz4_used for blocking
            plz4_used = plz4_used.where(~mask, ref_plz4)

            # Compute changed flag
            swis_changed = mask & (
                (street_before != street) |
                (house_before != house) |
                (plz4_before != plz4_used) |
                (ort_before != ort)
            )

            # Recompute address keys with updated fields
            street_key = normalize_street_key(street)
            street_sig = street_signature(street)
            house_num, house_sfx = parse_house_number(house)

    # Date of birth fields
    dob_ymd = parse_dob_ymd(df.get("Geburtstag", pd.Series([pd.NaT] * n)))
    jahrgang = df.get("Jahrgang", pd.Series([pd.NA] * n))
    yob = extract_yob(dob_ymd, jahrgang)

    # Legacy year field (for backward compatibility)
    year = yob.copy()

    # Build address keys for blocking
    # Building-level key: PLZ4 + street_key + house_num
    addr_key_building = (
        plz4_used + "|" + street_key + "|" + house_num
    ).astype("string")

    # Typo recovery key: PLZ4 + house_num + street_sig
    addr_key_typo = (
        plz4_used + "|" + house_num + "|" + street_sig
    ).astype("string")

    # Store in output dict
    out["first"] = first
    out["last"] = last
    out["name2"] = name2
    out["gender"] = gender
    out["street"] = street
    out["plz"] = plz
    out["house"] = house
    out["ort"] = ort
    out["full_name"] = (first + " " + last).astype("string")

    # Address blocking fields
    out["plz4_used"] = plz4_used
    out["street_key"] = street_key
    out["street_sig"] = street_sig
    out["house_num"] = house_num
    out["house_sfx"] = house_sfx
    out["addr_key_building"] = addr_key_building
    out["addr_key_typo"] = addr_key_typo

    # Swisstopo fields
    out["swis_match_type"] = swis_match_type
    out["swis_changed"] = swis_changed
    out["swis_adr_egaid_ref"] = swis_adr_egaid_ref
    out["swis_bdg_egid_ref"] = swis_bdg_egid_ref
    out["swis_street_label_ref"] = swis_street_label_ref
    out["swis_adr_number_ref"] = swis_adr_number_ref
    out["swis_plz4_ref"] = swis_plz4_ref
    out["swis_ort_ref"] = swis_ort_ref

    # Date fields
    out["dob_ymd"] = dob_ymd.to_numpy(dtype=np.int32, copy=False)
    out["yob"] = yob.to_numpy(dtype=np.int32, copy=False)
    out["year"] = year.to_numpy(dtype=np.int32, copy=False)  # legacy

    return out
