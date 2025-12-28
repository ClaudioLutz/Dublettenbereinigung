from __future__ import annotations

import re
import pandas as pd
import numpy as np
from unidecode import unidecode

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")

# Swiss multilingual street type tokens to normalize/remove
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
        
        # Remove street type tokens
        filtered = [t for t in tokens if t not in _STREET_TYPES]
        
        # Join remaining tokens
        return " ".join(filtered)
    
    return street.map(_process_street).astype("string")


def street_signature(street: pd.Series) -> pd.Series:
    """
    Create a street signature robust to minor typos for typo recovery.
    
    Strategy:
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
        
        # Remove street type tokens
        filtered = [t for t in tokens if t not in _STREET_TYPES]
        
        # Keep first 4 chars of each token
        prefixed = [t[:4] for t in filtered if t]
        
        # Sort tokens
        prefixed.sort()
        
        # Join with "-"
        return "-".join(prefixed)
    
    return street.map(_process_street).astype("string")


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


def preprocess(df: pd.DataFrame) -> dict[str, object]:
    """
    Preprocess dataframe with address-based blocking support.
    
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

    # Address fields - basic normalization
    street = _norm_series(df.get("Strasse", pd.Series([""] * n)))
    plz = _norm_series(df.get("Plz", pd.Series([""] * n)))
    house = _norm_series(df.get("HausNummer", pd.Series([""] * n)))
    ort = _norm_series(df.get("Ort", pd.Series([""] * n)))

    # Address-specific fields for blocking
    street_key = normalize_street_key(street)
    street_sig = street_signature(street)
    house_num, house_sfx = parse_house_number(house)
    
    # Date of birth fields
    dob_ymd = parse_dob_ymd(df.get("Geburtstag", pd.NaT))
    jahrgang = df.get("Jahrgang", pd.Series([pd.NA] * n))
    yob = extract_yob(dob_ymd, jahrgang)
    
    # Legacy year field (for backward compatibility)
    year = yob.copy()

    # Build address keys for blocking
    # Building-level key: PLZ + street_key + house_num
    addr_key_building = (
        plz + "|" + street_key + "|" + house_num
    ).astype("string")
    
    # Typo recovery key: PLZ + house_num + street_sig
    addr_key_typo = (
        plz + "|" + house_num + "|" + street_sig
    ).astype("string")

    # Store in output dict
    out["first"] = first
    out["last"] = last
    out["name2"] = name2
    out["street"] = street
    out["plz"] = plz
    out["house"] = house
    out["ort"] = ort
    out["full_name"] = (first + " " + last).astype("string")
    
    # Address blocking fields
    out["street_key"] = street_key
    out["street_sig"] = street_sig
    out["house_num"] = house_num
    out["house_sfx"] = house_sfx
    out["addr_key_building"] = addr_key_building
    out["addr_key_typo"] = addr_key_typo
    
    # Date fields
    out["dob_ymd"] = dob_ymd.to_numpy(dtype=np.int32, copy=False)
    out["yob"] = yob.to_numpy(dtype=np.int32, copy=False)
    out["year"] = year.to_numpy(dtype=np.int32, copy=False)  # legacy

    return out
