"""
Utility functions for pattern discovery analysis.

This module provides functions for:
- Loading and validating modular_results.csv
- Extracting 35+ boolean rule features from matched pairs
- Converting features to binary matrices for k-modes clustering
"""

import os
from datetime import datetime, timedelta
from typing import Dict
import pandas as pd
import numpy as np


def load_modular_results(filepath: str) -> pd.DataFrame:
    """
    Load and validate modular_results.csv from the main pipeline.

    Args:
        filepath: Path to modular_results.csv file

    Returns:
        DataFrame with validated pair data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If required columns are missing or data is invalid
    """
    # Check file exists
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    # Check file age (warn if >7 days old)
    file_mod_time = datetime.fromtimestamp(os.path.getmtime(filepath))
    if datetime.now() - file_mod_time > timedelta(days=7):
        print(f"WARNING: File is {(datetime.now() - file_mod_time).days} days old. "
              "Results may be stale. Consider re-running the main pipeline.")

    # Load CSV with error handling for malformed rows and encoding issues
    try:
        df = pd.read_csv(filepath)
    except (pd.errors.ParserError, UnicodeDecodeError) as e:
        print(f"WARNING: CSV loading error detected: {type(e).__name__}")
        print("Attempting to load with error tolerance and different encoding...")
        try:
            # Try with Latin-1 encoding and skip bad lines
            df = pd.read_csv(filepath, encoding='latin-1', on_bad_lines='skip', engine='python')
            print(f"Loaded {len(df)} rows with latin-1 encoding (some malformed rows may have been skipped)")
        except Exception as e2:
            # Try with Windows-1252 encoding
            print(f"Latin-1 failed, trying Windows-1252 encoding...")
            df = pd.read_csv(filepath, encoding='cp1252', on_bad_lines='skip', engine='python')
            print(f"Loaded {len(df)} rows with cp1252 encoding (some malformed rows may have been skipped)")

    # Validate required columns
    required_cols = ['i', 'j', 'score', 'name_score', 'addr_score', 'reason', 'is_swapped']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Validate data integrity
    if df['score'].isnull().any():
        print(f"WARNING: {df['score'].isnull().sum()} pairs have null scores")

    if not df['score'].between(0, 100, inclusive='both').all():
        invalid_scores = df[~df['score'].between(0, 100, inclusive='both')]
        print(f"WARNING: {len(invalid_scores)} pairs have scores outside 0-100 range")

    print(f"Loaded {len(df)} pairs from {filepath}")
    return df


def extract_rule_features(pair_row: pd.Series) -> Dict[str, bool]:
    """
    Extract 35+ boolean rule features from a matched pair.

    Features extracted:
    - Match type features (16): exact/fuzzy/address_assisted/phonetic_assisted × normal/swapped × gender variants
    - Hard gate features (4): DOB/YOB/house/zweitname conflicts
    - Data quality features (6): DOB/YOB presence and match quality
    - Similarity tier features (9+): name/address similarity tiers

    Args:
        pair_row: A row from modular_results.csv with pair data

    Returns:
        Dictionary mapping feature names to boolean values
    """
    features = {}

    # Extract basic fields
    reason = str(pair_row.get('reason', '')).lower()
    score = float(pair_row.get('score', 0))
    name_score = float(pair_row.get('name_score', 0))
    addr_score = float(pair_row.get('addr_score', 0))
    is_swapped = bool(pair_row.get('is_swapped', False))

    # Match Type Features (16)
    # Parse reason field to identify match type and gender variant
    features['exact_normal'] = (reason == 'exact_normal')
    features['exact_swapped'] = (reason == 'exact_swapped')
    features['exact_normal_different_gender'] = (reason == 'exact_normal_different_gender')
    features['exact_swapped_different_gender'] = (reason == 'exact_swapped_different_gender')

    features['fuzzy_normal'] = (reason == 'fuzzy_normal')
    features['fuzzy_swapped'] = (reason == 'fuzzy_swapped')
    features['fuzzy_normal_different_gender'] = (reason == 'fuzzy_normal_different_gender')
    features['fuzzy_swapped_different_gender'] = (reason == 'fuzzy_swapped_different_gender')

    features['address_assisted_normal'] = (reason == 'address_assisted_normal')
    features['address_assisted_swapped'] = (reason == 'address_assisted_swapped')
    features['address_assisted_normal_different_gender'] = (reason == 'address_assisted_normal_different_gender')
    features['address_assisted_swapped_different_gender'] = (reason == 'address_assisted_swapped_different_gender')

    features['phonetic_assisted_normal'] = (reason == 'phonetic_assisted_normal')
    features['phonetic_assisted_swapped'] = (reason == 'phonetic_assisted_swapped')
    features['phonetic_assisted_normal_different_gender'] = (reason == 'phonetic_assisted_normal_different_gender')
    features['phonetic_assisted_swapped_different_gender'] = (reason == 'phonetic_assisted_swapped_different_gender')

    # Hard Gate Features (4)
    # Note: Pairs that hit hard gates are rejected (None), so won't appear in modular_results.csv
    # These features will always be False for pairs that made it through scoring
    # We keep them for completeness and future ground truth labeling
    features['gate_dob_conflict'] = False  # Would be rejected before scoring
    features['gate_yob_conflict'] = False  # Would be rejected before scoring
    features['gate_house_conflict'] = False  # Would be rejected before scoring
    features['gate_zweitname_conflict'] = False  # Would be rejected before scoring

    # Data Quality Features (6)
    # Reconstruct DOB/YOB presence from pair data
    # NOTE: modular_results.csv doesn't include DOB fields directly
    # We infer from score patterns and reason codes

    # If exact match with high confidence, likely have DOB
    # If address_assisted or phonetic_assisted, might be missing DOB
    # These are approximations - actual extraction would require re-reading source data

    # For now, use heuristics based on match type
    is_exact_match = features['exact_normal'] or features['exact_swapped'] or \
                     features['exact_normal_different_gender'] or features['exact_swapped_different_gender']
    is_fuzzy_match = features['fuzzy_normal'] or features['fuzzy_swapped'] or \
                     features['fuzzy_normal_different_gender'] or features['fuzzy_swapped_different_gender']
    is_assisted_match = features['address_assisted_normal'] or features['address_assisted_swapped'] or \
                       features['address_assisted_normal_different_gender'] or features['address_assisted_swapped_different_gender'] or \
                       features['phonetic_assisted_normal'] or features['phonetic_assisted_swapped'] or \
                       features['phonetic_assisted_normal_different_gender'] or features['phonetic_assisted_swapped_different_gender']

    # Heuristic: exact matches likely have DOB, assisted matches likely missing DOB
    features['both_dob_missing'] = is_assisted_match  # Approximate
    features['one_dob_missing'] = False  # Would need source data
    features['both_have_exact_dob'] = is_exact_match and score >= 95  # High confidence exact match
    features['yob_only_match'] = is_fuzzy_match and score >= 85 and score < 95  # Approximate
    features['both_yob_missing'] = is_assisted_match  # Approximate
    features['one_yob_missing'] = False  # Would need source data

    # Similarity Tier Features (9+)
    # Name similarity tiers
    name_sim = name_score / 100.0  # Convert to 0-1 scale
    features['name_similarity_high'] = (name_sim >= 0.90)
    features['name_similarity_medium'] = (0.75 <= name_sim < 0.90)
    features['name_similarity_low'] = (name_sim < 0.75)

    # First/Last similarity (approximate from name_score)
    # Would need individual component scores for accurate extraction
    features['first_similarity_high'] = (name_sim >= 0.75)  # Approximate
    features['last_similarity_high'] = (name_sim >= 0.80)  # Approximate

    # Address similarity tiers
    addr_ratio = addr_score / 100.0  # Convert to 0-1 scale
    features['address_ratio_strong'] = (addr_ratio >= 0.9)
    features['address_ratio_moderate'] = (0.5 <= addr_ratio < 0.9)
    features['address_ratio_weak'] = (addr_ratio < 0.5)

    # Different genders at same address
    has_gender_suffix = '_different_gender' in reason
    features['different_genders_same_address'] = has_gender_suffix

    return features


def extract_features_for_all_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract rule features for all pairs in the DataFrame (VECTORIZED for speed).

    Args:
        df: DataFrame with pair data from modular_results.csv

    Returns:
        DataFrame with original columns plus 35+ boolean feature columns
    """
    print(f"Extracting rule features for {len(df)} pairs (vectorized)...")

    # Vectorized feature extraction (much faster than row-by-row)
    result_df = df.copy()

    # Match Type Features (16) - vectorized string matching
    reason_lower = df['reason'].str.lower()

    result_df['exact_normal'] = (reason_lower == 'exact_normal')
    result_df['exact_swapped'] = (reason_lower == 'exact_swapped')
    result_df['exact_normal_different_gender'] = (reason_lower == 'exact_normal_different_gender')
    result_df['exact_swapped_different_gender'] = (reason_lower == 'exact_swapped_different_gender')

    result_df['fuzzy_normal'] = (reason_lower == 'fuzzy_normal')
    result_df['fuzzy_swapped'] = (reason_lower == 'fuzzy_swapped')
    result_df['fuzzy_normal_different_gender'] = (reason_lower == 'fuzzy_normal_different_gender')
    result_df['fuzzy_swapped_different_gender'] = (reason_lower == 'fuzzy_swapped_different_gender')

    result_df['address_assisted_normal'] = (reason_lower == 'address_assisted_normal')
    result_df['address_assisted_swapped'] = (reason_lower == 'address_assisted_swapped')
    result_df['address_assisted_normal_different_gender'] = (reason_lower == 'address_assisted_normal_different_gender')
    result_df['address_assisted_swapped_different_gender'] = (reason_lower == 'address_assisted_swapped_different_gender')

    result_df['phonetic_assisted_normal'] = (reason_lower == 'phonetic_assisted_normal')
    result_df['phonetic_assisted_swapped'] = (reason_lower == 'phonetic_assisted_swapped')
    result_df['phonetic_assisted_normal_different_gender'] = (reason_lower == 'phonetic_assisted_normal_different_gender')
    result_df['phonetic_assisted_swapped_different_gender'] = (reason_lower == 'phonetic_assisted_swapped_different_gender')

    # Hard Gate Features (4) - always False for pairs that made it through
    result_df['gate_dob_conflict'] = False
    result_df['gate_yob_conflict'] = False
    result_df['gate_house_conflict'] = False
    result_df['gate_zweitname_conflict'] = False

    # Data Quality Features (6) - vectorized boolean logic
    is_exact = result_df['exact_normal'] | result_df['exact_swapped'] | result_df['exact_normal_different_gender'] | result_df['exact_swapped_different_gender']
    is_fuzzy = result_df['fuzzy_normal'] | result_df['fuzzy_swapped'] | result_df['fuzzy_normal_different_gender'] | result_df['fuzzy_swapped_different_gender']
    is_assisted = result_df['address_assisted_normal'] | result_df['address_assisted_swapped'] | result_df['address_assisted_normal_different_gender'] | result_df['address_assisted_swapped_different_gender'] | result_df['phonetic_assisted_normal'] | result_df['phonetic_assisted_swapped'] | result_df['phonetic_assisted_normal_different_gender'] | result_df['phonetic_assisted_swapped_different_gender']

    result_df['both_dob_missing'] = is_assisted
    result_df['one_dob_missing'] = False
    result_df['both_have_exact_dob'] = is_exact & (df['score'] >= 95)
    result_df['yob_only_match'] = is_fuzzy & (df['score'] >= 85) & (df['score'] < 95)
    result_df['both_yob_missing'] = is_assisted
    result_df['one_yob_missing'] = False

    # Similarity Tier Features (9+) - vectorized comparisons
    name_sim = df['name_score'] / 100.0
    addr_ratio = df['addr_score'] / 100.0

    result_df['name_similarity_high'] = (name_sim >= 0.90)
    result_df['name_similarity_medium'] = (name_sim >= 0.75) & (name_sim < 0.90)
    result_df['name_similarity_low'] = (name_sim < 0.75)

    result_df['first_similarity_high'] = (name_sim >= 0.75)
    result_df['last_similarity_high'] = (name_sim >= 0.80)

    result_df['address_ratio_strong'] = (addr_ratio >= 0.9)
    result_df['address_ratio_moderate'] = (addr_ratio >= 0.5) & (addr_ratio < 0.9)
    result_df['address_ratio_weak'] = (addr_ratio < 0.5)

    result_df['different_genders_same_address'] = reason_lower.str.contains('_different_gender')

    feature_cols = [
        'exact_normal', 'exact_swapped', 'exact_normal_different_gender', 'exact_swapped_different_gender',
        'fuzzy_normal', 'fuzzy_swapped', 'fuzzy_normal_different_gender', 'fuzzy_swapped_different_gender',
        'address_assisted_normal', 'address_assisted_swapped', 'address_assisted_normal_different_gender', 'address_assisted_swapped_different_gender',
        'phonetic_assisted_normal', 'phonetic_assisted_swapped', 'phonetic_assisted_normal_different_gender', 'phonetic_assisted_swapped_different_gender',
        'gate_dob_conflict', 'gate_yob_conflict', 'gate_house_conflict', 'gate_zweitname_conflict',
        'both_dob_missing', 'one_dob_missing', 'both_have_exact_dob', 'yob_only_match', 'both_yob_missing', 'one_yob_missing',
        'name_similarity_high', 'name_similarity_medium', 'name_similarity_low',
        'first_similarity_high', 'last_similarity_high',
        'address_ratio_strong', 'address_ratio_moderate', 'address_ratio_weak',
        'different_genders_same_address'
    ]

    print(f"Extracted {len(feature_cols)} features for {len(result_df)} pairs (vectorized)")
    return result_df


def convert_features_to_binary_matrix(df: pd.DataFrame, feature_columns: list = None) -> np.ndarray:
    """
    Convert boolean feature columns to binary (0/1) numpy array for k-modes.

    Args:
        df: DataFrame with boolean feature columns
        feature_columns: List of feature column names to include (default: all columns starting with known prefixes)

    Returns:
        Numpy array of shape (n_pairs, n_features) with 0/1 integer values
    """
    if feature_columns is None:
        # Auto-detect feature columns based on naming patterns
        feature_prefixes = [
            'exact_', 'fuzzy_', 'address_assisted_', 'phonetic_assisted_',
            'gate_', 'both_', 'one_', 'yob_only_',
            'name_similarity_', 'first_similarity_', 'last_similarity_',
            'address_ratio_', 'different_genders_'
        ]
        feature_columns = [col for col in df.columns
                          if any(col.startswith(prefix) for prefix in feature_prefixes)]

    # Extract feature columns and convert to 0/1 integers
    feature_matrix = df[feature_columns].astype(int).values

    print(f"Converted {len(feature_columns)} features to binary matrix: shape {feature_matrix.shape}")
    return feature_matrix


def get_feature_names() -> list:
    """
    Return the canonical list of 35+ feature names in extraction order.

    Returns:
        List of feature names as strings
    """
    return [
        # Match Type Features (16)
        'exact_normal',
        'exact_swapped',
        'exact_normal_different_gender',
        'exact_swapped_different_gender',
        'fuzzy_normal',
        'fuzzy_swapped',
        'fuzzy_normal_different_gender',
        'fuzzy_swapped_different_gender',
        'address_assisted_normal',
        'address_assisted_swapped',
        'address_assisted_normal_different_gender',
        'address_assisted_swapped_different_gender',
        'phonetic_assisted_normal',
        'phonetic_assisted_swapped',
        'phonetic_assisted_normal_different_gender',
        'phonetic_assisted_swapped_different_gender',

        # Hard Gate Features (4)
        'gate_dob_conflict',
        'gate_yob_conflict',
        'gate_house_conflict',
        'gate_zweitname_conflict',

        # Data Quality Features (6)
        'both_dob_missing',
        'one_dob_missing',
        'both_have_exact_dob',
        'yob_only_match',
        'both_yob_missing',
        'one_yob_missing',

        # Similarity Tier Features (9)
        'name_similarity_high',
        'name_similarity_medium',
        'name_similarity_low',
        'first_similarity_high',
        'last_similarity_high',
        'address_ratio_strong',
        'address_ratio_moderate',
        'address_ratio_weak',
        'different_genders_same_address',
    ]


def stratified_sample_from_clusters(
    df: pd.DataFrame,
    cluster_column: str = 'cluster',
    samples_per_cluster: int = 15,
    random_state: int = 42
) -> pd.DataFrame:
    """
    Sample N pairs from each cluster for stratified analysis.

    Args:
        df: DataFrame with cluster assignments
        cluster_column: Name of cluster column (default: 'cluster')
        samples_per_cluster: Number of samples per cluster (default: 15)
        random_state: Random seed for reproducibility (default: 42)

    Returns:
        DataFrame with sampled pairs and cluster_size metadata
    """
    print(f"Stratified sampling: {samples_per_cluster} pairs per cluster...")

    if cluster_column not in df.columns:
        raise ValueError(f"Cluster column '{cluster_column}' not found in DataFrame")

    sampled_dfs = []
    cluster_metadata = []

    for cluster_id in sorted(df[cluster_column].unique()):
        cluster_df = df[df[cluster_column] == cluster_id]
        cluster_size = len(cluster_df)

        if cluster_size == 0:
            print(f"  WARNING: Cluster {cluster_id} has 0 pairs, skipping")
            continue
        elif cluster_size < samples_per_cluster:
            print(f"  Cluster {cluster_id}: Sampling ALL {cluster_size} pairs (< {samples_per_cluster})")
            sampled = cluster_df.copy()
        else:
            print(f"  Cluster {cluster_id}: Sampling {samples_per_cluster}/{cluster_size} pairs")
            sampled = cluster_df.sample(n=samples_per_cluster, random_state=random_state)

        # Add cluster size metadata
        sampled = sampled.copy()
        sampled['cluster_size'] = cluster_size

        sampled_dfs.append(sampled)
        cluster_metadata.append({
            'cluster_id': cluster_id,
            'total_size': cluster_size,
            'sampled_size': len(sampled)
        })

    # Combine all samples
    result_df = pd.concat(sampled_dfs, ignore_index=True)

    print(f"\nSampling complete:")
    print(f"  Total clusters: {len(cluster_metadata)}")
    print(f"  Total samples: {len(result_df)}")
    print(f"  Target per cluster: {samples_per_cluster}")

    return result_df
