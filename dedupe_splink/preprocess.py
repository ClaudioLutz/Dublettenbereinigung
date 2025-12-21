# dedupe_splink/preprocess.py
from __future__ import annotations
import re
import pandas as pd

_UMLAUTS = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",
    "ß": "ss",
})

_non_alnum = re.compile(r"[^a-z0-9 ]+")

def _norm_text(s: pd.Series) -> pd.Series:
    s = s.fillna("").astype(str)
    s = s.str.translate(_UMLAUTS)
    s = s.str.lower()
    s = s.str.replace(r"\s+", " ", regex=True).str.strip()
    s = s.str.replace(_non_alnum, "", regex=True)
    return s

def _norm_plz(s: pd.Series) -> pd.Series:
    s = s.fillna("").astype(str)
    s = s.str.replace(r"\D+", "", regex=True)
    # pad to 5 if numeric-ish
    s = s.str[-5:].str.zfill(5)
    # treat empty / all zeros as missing
    s = s.where(s.str.len() == 5, "")
    s = s.where(s != "00000", "")
    return s

def _norm_house(s: pd.Series) -> pd.Series:
    s = s.fillna("").astype(str).str.lower()
    s = s.str.replace(r"\s+", "", regex=True)
    s = s.str.replace(r"[^0-9a-z]", "", regex=True)
    return s

def _year_from_jahrgang(df: pd.DataFrame, col: str) -> pd.Series:
    # If it's already a year, keep it; if it's date, take year.
    s = df.get(col, pd.Series([""] * len(df)))
    s = pd.to_numeric(s, errors="coerce")
    return s.fillna(0).astype(int).where(lambda x: (x >= 1850) & (x <= 2100), 0)

def preprocess_chunk(
    df: pd.DataFrame,
    unique_id_col: str = "unique_id",
    col_first: str = "Vorname",
    col_last: str = "Name",
    col_last2: str = "Name2",
    col_street: str = "Strasse",
    col_house: str = "HausNummer",
    col_plz: str = "Plz",
    col_year: str = "Jahrgang",
) -> pd.DataFrame:
    out = df.copy()

    out["first_name_norm"] = _norm_text(out.get(col_first, ""))
    out["surname_norm"] = _norm_text(out.get(col_last, ""))
    out["surname2_norm"] = _norm_text(out.get(col_last2, ""))

    out["street_norm"] = _norm_text(out.get(col_street, ""))
    out["house_norm"] = _norm_house(out.get(col_house, ""))

    out["plz_norm"] = _norm_plz(out.get(col_plz, ""))
    out["plz_prefix2"] = out["plz_norm"].str[:2]
    out["plz_prefix3"] = out["plz_norm"].str[:3]

    out["birth_year"] = _year_from_jahrgang(out, col_year)

    # initials / short keys for cheap blocking
    out["surname_initial"] = out["surname_norm"].str[:1]
    out["surname_prefix4"] = out["surname_norm"].str[:4]
    out["first_initial"] = out["first_name_norm"].str[:1]

    # Shard key: keep bounded partitions
    out["shard"] = out["plz_prefix2"].where(out["plz_prefix2"] != "", "no_plz")

    # Keep only needed columns + unique id + raw columns optionally
    # (You can drop raw columns here to reduce size.)
    return out
