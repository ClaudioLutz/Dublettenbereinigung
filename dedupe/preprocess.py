from __future__ import annotations

import re
import pandas as pd
import numpy as np
from unidecode import unidecode

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


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


def preprocess(df: pd.DataFrame) -> dict[str, object]:
    out: dict[str, object] = {}
    n = len(df)

    first = _norm_series(df["Vorname"])
    last = _norm_series(df["Name"])
    name2 = _norm_series(df.get("Name2", pd.Series([""] * n)))

    street = _norm_series(df.get("Strasse", pd.Series([""] * n)))
    plz = _norm_series(df.get("Plz", pd.Series([""] * n)))
    house = _norm_series(df.get("HausNummer", pd.Series([""] * n)))

    year = pd.to_datetime(df.get("Geburtstag", pd.NaT), errors="coerce").dt.year
    year = year.fillna(-1).astype("int32")

    out["first"] = first
    out["last"] = last
    out["name2"] = name2
    out["street"] = street
    out["plz"] = plz
    out["house"] = house
    out["year"] = year.to_numpy(dtype=np.int32, copy=False)

    out["full_name"] = (first + " " + last).astype("string")

    return out
