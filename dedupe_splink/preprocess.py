import pandas as pd
import numpy as np
from unidecode import unidecode
import re
import cologne_phonetics

def preprocess_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies deterministic normalization to the DataFrame.
    Returns a new DataFrame with added normalized columns.
    """
    df = df.copy()

    def normalize_str(series):
        s = series.astype(str).fillna("")
        s = s.str.lower().str.strip()
        # Apply unidecode to handle accents
        s = s.apply(lambda x: unidecode(x) if isinstance(x, str) else x)
        # Keep alphanumeric
        s = s.str.replace(r'[^a-z0-9]', '', regex=True)
        return s

    def normalize_plz(series):
        s = series.astype(str).fillna("").str.strip()
        s = s.str.replace(r'\D', '', regex=True)
        s = s.replace({'nan': '', 'None': ''})
        # If valid length (1-5), pad with zeros to 5
        mask = (s.str.len() > 0) & (s.str.len() <= 5)
        s.loc[mask] = s.loc[mask].str.zfill(5)
        # Invalid length (>5 or 0) -> empty
        s.loc[~mask & (s != '')] = ''
        return s

    # Safe get column
    def get_col(name):
        return df[name] if name in df.columns else pd.Series([""] * len(df), index=df.index)

    df['first_name_norm'] = normalize_str(get_col('Vorname'))
    df['surname_norm'] = normalize_str(get_col('Name'))
    df['surname2_norm'] = normalize_str(get_col('Name2'))
    df['street_norm'] = normalize_str(get_col('Strasse'))
    df['house_norm'] = normalize_str(get_col('HausNummer'))
    df['plz_norm'] = normalize_plz(get_col('Plz'))

    df['plz_prefix2'] = df['plz_norm'].str[:2]
    df['plz_prefix3'] = df['plz_norm'].str[:3]

    # Birth Year
    if 'Geburtstag' in df.columns:
        dates = pd.to_datetime(df['Geburtstag'], errors='coerce')
        years = dates.dt.year
        # If year is NaN, try Jahrgang
        if 'Jahrgang' in df.columns:
             jg = pd.to_numeric(df['Jahrgang'], errors='coerce')
             years = years.fillna(jg)

        df['birth_year'] = years.fillna(-1).astype(int).astype(str).replace('-1', '')
    elif 'Jahrgang' in df.columns:
        df['birth_year'] = pd.to_numeric(df['Jahrgang'], errors='coerce').fillna(-1).astype(int).astype(str).replace('-1', '')
    else:
        df['birth_year'] = ''

    # Surname Initial
    df['surname_initial'] = df['surname_norm'].str[:1]

    # Phonetic
    def get_phonetic(name):
        if not name:
            return ""
        try:
            codes = cologne_phonetics.encode(name)
            if codes:
                return codes[0][1] # tuple (name_part, code)
            return ""
        except:
            return ""

    df['surname_phonetic'] = df['surname_norm'].apply(get_phonetic)

    return df
