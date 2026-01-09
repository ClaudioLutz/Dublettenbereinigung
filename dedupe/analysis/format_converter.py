"""
Format converter for results_with_gender.csv to pattern discovery format.

Converts the two-row-per-match format to the single-row-per-pair format
expected by the pattern discovery module.
"""

import pandas as pd


def convert_results_with_gender_to_pairs(filepath: str) -> pd.DataFrame:
    """
    Convert results_with_gender.csv format to pattern discovery pair format.

    The input format has two rows per match (position A and B).
    The output format has one row per pair with i, j, score, etc.

    Args:
        filepath: Path to results_with_gender.csv

    Returns:
        DataFrame with columns: i, j, score, name_score, addr_score, reason, is_swapped
    """
    print(f"Loading and converting {filepath}...")

    # Load the file
    df = pd.read_csv(filepath)

    print(f"Loaded {len(df)} rows ({len(df) // 2} matches)")

    # Separate position A and B
    df_a = df[df['position'] == 'A'].copy()
    df_b = df[df['position'] == 'B'].copy()

    # Merge on match_id to create pairs
    pairs = pd.merge(
        df_a,
        df_b,
        on='match_id',
        suffixes=('_i', '_j')
    )

    # Create the expected columns
    result_df = pd.DataFrame()

    # Pair indices (from the index column)
    result_df['i'] = pairs['index_i']
    result_df['j'] = pairs['index_j']

    # Score (use confidence from position A - they're the same)
    result_df['score'] = pairs['confidence_i']

    # For now, set name_score and addr_score to score (we don't have separate scores)
    # This is an approximation - the pattern discovery will still work
    result_df['name_score'] = pairs['confidence_i']
    result_df['addr_score'] = pairs['confidence_i']

    # Reason (use match_type from position A - they're the same)
    result_df['reason'] = pairs['match_type_i']

    # Determine is_swapped from match_type
    result_df['is_swapped'] = pairs['match_type_i'].str.contains('swapped')

    # Copy other useful columns for analysis
    result_df['vorname_i'] = pairs['vorname_i']
    result_df['name_i'] = pairs['name_i']
    result_df['vorname_j'] = pairs['vorname_j']
    result_df['name_j'] = pairs['name_j']

    result_df['strasse_i'] = pairs['strasse_i']
    result_df['hausnummer_i'] = pairs['hausnummer_i']
    result_df['plz_i'] = pairs['plz_i']
    result_df['ort_i'] = pairs['ort_i']

    result_df['strasse_j'] = pairs['strasse_j']
    result_df['hausnummer_j'] = pairs['hausnummer_j']
    result_df['plz_j'] = pairs['plz_j']
    result_df['ort_j'] = pairs['ort_j']

    result_df['geburtstag_i'] = pairs['geburtstag_i']
    result_df['geburtstag_j'] = pairs['geburtstag_j']

    result_df['jahrgang_i'] = pairs['jahrgang_i']
    result_df['jahrgang_j'] = pairs['jahrgang_j']

    print(f"Converted to {len(result_df)} pair rows")
    print(f"Score range: {result_df['score'].min():.1f} - {result_df['score'].max():.1f}")
    print(f"Match types: {result_df['reason'].value_counts().to_dict()}")

    return result_df
