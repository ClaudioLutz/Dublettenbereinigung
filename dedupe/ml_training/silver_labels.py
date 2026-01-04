"""
Silver label generation from existing rule-based matches (weak supervision).

This module generates training data without manual labeling by using
high-confidence matches from the existing rule-based system as positive labels
and same-block non-matches as negative labels.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SilverLabelGenerator:
    """
    Generate silver labels from rule-based deduplication results.

    Uses weak supervision strategy:
    - Positives: High-confidence matches (exact_normal, exact_swapped, confidence ≥95%)
    - Negatives: Same-block non-matches (hard negatives for better discrimination)
    """

    def __init__(
        self,
        positive_confidence_threshold: float = 95.0,
        positive_match_types: Optional[List[str]] = None,
        negative_ratio: float = 2.5,
        hard_negative_strategy: str = 'blocking',
    ):
        """
        Initialize silver label generator.

        Args:
            positive_confidence_threshold: Minimum confidence for positive labels
            positive_match_types: Match types to include (default: exact matches only)
            negative_ratio: Ratio of negatives to positives (e.g., 2.5 = 2.5:1)
            hard_negative_strategy: Strategy for generating negatives
                                   ('blocking', 'random', 'mixed')
        """
        self.positive_confidence_threshold = positive_confidence_threshold
        self.positive_match_types = positive_match_types or [
            'exact_normal',
            'exact_swapped',
        ]
        self.negative_ratio = negative_ratio
        self.hard_negative_strategy = hard_negative_strategy

    def _read_csv_with_encoding(self, file_path: str) -> pd.DataFrame:
        """
        Read CSV file trying multiple encodings for Windows compatibility.

        Args:
            file_path: Path to CSV file

        Returns:
            DataFrame with CSV contents
        """
        encodings_to_try = ['utf-8', 'latin-1', 'cp1252']

        for encoding in encodings_to_try:
            try:
                df = pd.read_csv(file_path, sep=';', encoding=encoding)
                logger.debug(f"Successfully read CSV with encoding: {encoding}")
                return df
            except UnicodeDecodeError:
                continue
            except Exception:
                # Try comma-separated with same encoding
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    logger.debug(f"Successfully read CSV (comma-sep) with encoding: {encoding}")
                    return df
                except:
                    continue

        raise ValueError(f"Could not read {file_path} with any supported encoding")

    def extract_positives_from_results(
        self,
        results_path: str,
    ) -> pd.DataFrame:
        """
        Extract positive pairs from rule-based deduplication results.

        Args:
            results_path: Path to results CSV (e.g., modular_results.csv)

        Returns:
            DataFrame with columns: idx_a, idx_b, label, source, confidence, match_type
        """
        logger.info(f"Loading results from {results_path}")

        # Read CSV with encoding detection for Windows compatibility
        df = self._read_csv_with_encoding(results_path)

        logger.info(f"Loaded {len(df)} result rows")

        # Filter high-confidence matches
        high_conf_mask = (
            (df['confidence'] >= self.positive_confidence_threshold) &
            (df['match_type'].isin(self.positive_match_types))
        )

        high_conf_df = df[high_conf_mask].copy()
        logger.info(
            f"Found {len(high_conf_df)} high-confidence rows "
            f"(confidence ≥{self.positive_confidence_threshold})"
        )

        # Each match has 2 rows (position A and B)
        # Group by match_id to create pairs
        positives = []

        for match_id, group in high_conf_df.groupby('match_id'):
            if len(group) != 2:
                logger.warning(f"Match {match_id} has {len(group)} rows (expected 2), skipping")
                continue

            # Get A and B records
            row_a = group[group['position'] == 'A']
            row_b = group[group['position'] == 'B']

            if len(row_a) == 0 or len(row_b) == 0:
                logger.warning(f"Match {match_id} missing A or B position, skipping")
                continue

            row_a = row_a.iloc[0]
            row_b = row_b.iloc[0]

            positives.append({
                'idx_a': int(row_a['index']),
                'idx_b': int(row_b['index']),
                'label': 1,
                'source': 'deterministic',
                'confidence': float(row_a['confidence']),
                'match_type': str(row_a['match_type']),
                'crefo_a': str(row_a['crefo']),
                'crefo_b': str(row_b['crefo']),
            })

        positives_df = pd.DataFrame(positives)
        logger.info(f"Extracted {len(positives_df)} positive pairs")

        return positives_df

    def generate_hard_negatives_from_blocking(
        self,
        positives_df: pd.DataFrame,
        results_path: str,
        target_count: int,
    ) -> pd.DataFrame:
        """
        Generate hard negatives from same blocking partitions.

        Strategy: Sample pairs that share the same address block (same building)
        but were NOT matched by the rule-based system.

        Args:
            positives_df: DataFrame of positive pairs
            results_path: Path to results CSV
            target_count: Number of negative pairs to generate

        Returns:
            DataFrame with columns: idx_a, idx_b, label, source
        """
        logger.info("Generating hard negatives from blocking partitions")

        # Read full results to get all candidates (including non-matches)
        # Try multiple encodings for Windows-generated CSVs
        df = self._read_csv_with_encoding(results_path)

        # Get all unique indices
        all_indices_a = set(df['index'].unique())

        # Get positive pairs (to exclude)
        positive_pairs = set(
            (min(row['idx_a'], row['idx_b']), max(row['idx_a'], row['idx_b']))
            for _, row in positives_df.iterrows()
        )

        # Group by address blocking key
        negatives = []

        if 'addr_key_building' in df.columns:
            for block_key, group in df.groupby('addr_key_building'):
                if len(group) < 2:
                    continue

                # Get unique indices in this block
                indices_in_block = group['index'].unique()

                if len(indices_in_block) < 2:
                    continue

                # Sample pairs from this block
                for _ in range(min(5, len(indices_in_block))):  # Limit samples per block
                    # Random pair
                    idx_sample = np.random.choice(indices_in_block, size=2, replace=False)
                    idx_a, idx_b = sorted(idx_sample)

                    # Check if this is not a positive pair
                    if (idx_a, idx_b) not in positive_pairs:
                        negatives.append({
                            'idx_a': int(idx_a),
                            'idx_b': int(idx_b),
                            'label': 0,
                            'source': 'hard_negative_blocking',
                        })

                        if len(negatives) >= target_count:
                            break

                if len(negatives) >= target_count:
                    break

        # If we don't have enough, sample random pairs
        while len(negatives) < target_count:
            indices_list = list(all_indices_a)
            if len(indices_list) < 2:
                break

            idx_a, idx_b = np.random.choice(indices_list, size=2, replace=False)
            idx_a, idx_b = sorted([idx_a, idx_b])

            if (idx_a, idx_b) not in positive_pairs:
                negatives.append({
                    'idx_a': int(idx_a),
                    'idx_b': int(idx_b),
                    'label': 0,
                    'source': 'random_negative',
                })

        # Sample to exact target count
        if len(negatives) > target_count:
            negatives = np.random.choice(negatives, size=target_count, replace=False).tolist()

        negatives_df = pd.DataFrame(negatives)
        logger.info(f"Generated {len(negatives_df)} negative pairs")

        return negatives_df

    def generate_negatives_from_low_confidence(
        self,
        positives_df: pd.DataFrame,
        results_path: str,
        target_count: int,
        max_confidence: float = 70.0,
    ) -> pd.DataFrame:
        """
        Generate negatives from low-confidence matches.

        These are pairs that scored poorly in the rule-based system and are
        likely non-matches.

        Args:
            positives_df: DataFrame of positive pairs
            results_path: Path to results CSV
            target_count: Number of negative pairs to generate
            max_confidence: Maximum confidence for negative sampling

        Returns:
            DataFrame with negative pairs
        """
        logger.info("Generating negatives from low-confidence matches")

        # Read CSV with encoding detection for Windows compatibility
        df = self._read_csv_with_encoding(results_path)

        # Filter low-confidence matches
        low_conf_mask = df['confidence'] < max_confidence
        low_conf_df = df[low_conf_mask].copy()

        logger.info(f"Found {len(low_conf_df)} low-confidence rows (confidence < {max_confidence})")

        # Get positive pairs to exclude
        positive_pairs = set(
            (min(row['idx_a'], row['idx_b']), max(row['idx_a'], row['idx_b']))
            for _, row in positives_df.iterrows()
        )

        negatives = []

        for match_id, group in low_conf_df.groupby('match_id'):
            if len(group) != 2:
                continue

            row_a = group[group['position'] == 'A']
            row_b = group[group['position'] == 'B']

            if len(row_a) == 0 or len(row_b) == 0:
                continue

            row_a = row_a.iloc[0]
            row_b = row_b.iloc[0]

            idx_a = int(row_a['index'])
            idx_b = int(row_b['index'])
            pair = tuple(sorted([idx_a, idx_b]))

            # Exclude if it's a positive pair
            if pair not in positive_pairs:
                negatives.append({
                    'idx_a': pair[0],
                    'idx_b': pair[1],
                    'label': 0,
                    'source': 'low_confidence',
                    'confidence': float(row_a['confidence']),
                })

            if len(negatives) >= target_count:
                break

        negatives_df = pd.DataFrame(negatives)
        logger.info(f"Generated {len(negatives_df)} negatives from low-confidence matches")

        return negatives_df

    def generate_silver_labels(
        self,
        results_path: str,
        output_path: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Generate complete silver label dataset.

        Args:
            results_path: Path to rule-based results CSV
            output_path: Optional path to save combined labels

        Returns:
            Tuple of (positives_df, negatives_df, combined_df)
        """
        logger.info("=" * 80)
        logger.info("SILVER LABEL GENERATION")
        logger.info("=" * 80)

        # Extract positives
        positives_df = self.extract_positives_from_results(results_path)

        # Calculate target negative count
        target_negatives = int(len(positives_df) * self.negative_ratio)
        logger.info(
            f"Target: {len(positives_df)} positives, {target_negatives} negatives "
            f"(ratio: 1:{self.negative_ratio})"
        )

        # Generate negatives based on strategy
        if self.hard_negative_strategy == 'blocking':
            negatives_df = self.generate_hard_negatives_from_blocking(
                positives_df, results_path, target_negatives
            )
        elif self.hard_negative_strategy == 'low_confidence':
            negatives_df = self.generate_negatives_from_low_confidence(
                positives_df, results_path, target_negatives
            )
        elif self.hard_negative_strategy == 'mixed':
            # 50% from blocking, 50% from low confidence
            neg_blocking = self.generate_hard_negatives_from_blocking(
                positives_df, results_path, target_negatives // 2
            )
            neg_low_conf = self.generate_negatives_from_low_confidence(
                positives_df, results_path, target_negatives - len(neg_blocking)
            )
            negatives_df = pd.concat([neg_blocking, neg_low_conf], ignore_index=True)
        else:
            raise ValueError(f"Unknown hard_negative_strategy: {self.hard_negative_strategy}")

        # Combine
        combined_df = pd.concat([positives_df, negatives_df], ignore_index=True)

        # Shuffle
        combined_df = combined_df.sample(frac=1, random_state=42).reset_index(drop=True)

        logger.info("=" * 80)
        logger.info("SILVER LABEL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Positives: {len(positives_df):,}")
        logger.info(f"Negatives: {len(negatives_df):,}")
        logger.info(f"Total: {len(combined_df):,}")
        logger.info(f"Ratio: 1:{len(negatives_df) / len(positives_df):.2f}")
        logger.info("=" * 80)

        # Save if path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            combined_df.to_csv(output_path, index=False)
            logger.info(f"Saved silver labels to {output_path}")

            # Also save separate files for analysis
            positives_path = output_path.parent / f"{output_path.stem}_positives.csv"
            negatives_path = output_path.parent / f"{output_path.stem}_negatives.csv"

            positives_df.to_csv(positives_path, index=False)
            negatives_df.to_csv(negatives_path, index=False)

            logger.info(f"Saved positives to {positives_path}")
            logger.info(f"Saved negatives to {negatives_path}")

        return positives_df, negatives_df, combined_df
