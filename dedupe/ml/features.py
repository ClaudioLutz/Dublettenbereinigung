"""
Feature extraction for ML-based entity matching.

This module extracts features from record pairs, combining:
- Existing rule-based fuzzy matching scores
- Address similarity metrics
- Date/birth data features
- Embedding-based semantic similarity

Features are designed to work with LightGBM and respect business rules.
"""

import logging
from typing import Dict, Optional, Tuple

import numpy as np
from rapidfuzz import fuzz

from dedupe.scoring import (
    check_zweitname,
    compare_names_with_swap,
    get_first_word_bonus,
)

logger = logging.getLogger(__name__)

try:
    from dedupe.ml.config import EMBEDDING_DIM
except ImportError:
    EMBEDDING_DIM = 384


class FeatureExtractor:
    """
    Extract features from record pairs for ML model training and inference.

    This class combines rule-based features from the existing scoring system
    with new embedding-based features.
    """

    # Feature names (for interpretability and model training)
    FEATURE_NAMES = [
        # Name similarity features (8)
        'name_wratio_normal',
        'name_wratio_swapped',
        'first_wratio_normal',
        'first_wratio_swapped',
        'last_wratio_normal',
        'last_wratio_swapped',
        'cologne_first_match',
        'cologne_last_match',

        # Name2/Zweitname features (2)
        'name2_present_both',
        'name2_conflict',

        # Address similarity features (8)
        'plz_exact_match',
        'plz_region_match',
        'house_exact_match',
        'street_wratio',
        'ort_wratio',
        'addr_key_match',
        'street_sig_match',
        'address_composite_score',

        # Date/birth features (6)
        'dob_exact_match',
        'yob_exact_match',
        'dob_both_present',
        'dob_one_missing',
        'yob_both_present',
        'yob_one_missing',

        # Full embedding features (4) - includes name + address
        'emb_cosine_similarity',
        'emb_l2_distance',
        'emb_dot_product',
        'emb_manhattan_distance',

        # Name-only embedding features (4) - critical for name matching
        # These use embeddings generated only from name fields, no address
        'name_emb_cosine_similarity',
        'name_emb_l2_distance',
        'name_emb_dot_product',
        'name_emb_manhattan_distance',

        # Interaction features (2)
        'name_addr_interaction',
        'first_word_bonus',
    ]

    def __init__(self, embedding_store=None, name_embedding_store=None):
        """
        Initialize feature extractor.

        Args:
            embedding_store: Optional EmbeddingStore for full (name+address) embeddings
            name_embedding_store: Optional EmbeddingStore for name-only embeddings.
                                  This is critical for proper entity matching as it
                                  provides name similarity without address contamination.
        """
        self.embedding_store = embedding_store
        self.name_embedding_store = name_embedding_store
        self.n_features = len(self.FEATURE_NAMES)

    def extract_features(
        self,
        idx_a: int,
        idx_b: int,
        cols: Dict,
        include_embeddings: bool = True,
    ) -> Dict[str, float]:
        """
        Extract all features for a pair of records.

        Args:
            idx_a: Index of first record
            idx_b: Index of second record
            cols: Dictionary of preprocessed columns/arrays
            include_embeddings: Whether to include embedding features

        Returns:
            Dictionary mapping feature names to values
        """
        features = {}

        # Extract name features
        name_features = self._extract_name_features(idx_a, idx_b, cols)
        features.update(name_features)

        # Extract address features
        addr_features = self._extract_address_features(idx_a, idx_b, cols)
        features.update(addr_features)

        # Extract date/birth features
        date_features = self._extract_date_features(idx_a, idx_b, cols)
        features.update(date_features)

        # Extract full embedding features (name + address)
        if include_embeddings and self.embedding_store is not None:
            emb_features = self._extract_embedding_features(idx_a, idx_b)
            features.update(emb_features)
        else:
            # Fill with default values if embeddings not available
            features.update({
                'emb_cosine_similarity': 0.0,
                'emb_l2_distance': 0.0,
                'emb_dot_product': 0.0,
                'emb_manhattan_distance': 0.0,
            })

        # Extract name-only embedding features (critical for name matching)
        if include_embeddings and self.name_embedding_store is not None:
            name_emb_features = self._extract_name_embedding_features(idx_a, idx_b)
            features.update(name_emb_features)
        else:
            # Fill with default values if name embeddings not available
            features.update({
                'name_emb_cosine_similarity': 0.0,
                'name_emb_l2_distance': 0.0,
                'name_emb_dot_product': 0.0,
                'name_emb_manhattan_distance': 0.0,
            })

        # Extract interaction features
        interaction_features = self._extract_interaction_features(
            idx_a, idx_b, cols, name_features, addr_features
        )
        features.update(interaction_features)

        return features

    def _extract_name_features(
        self,
        idx_a: int,
        idx_b: int,
        cols: Dict,
    ) -> Dict[str, float]:
        """Extract name similarity features."""
        features = {}

        # Get normalized names
        first_a = cols['first'][idx_a]
        last_a = cols['last'][idx_a]
        name2_a = cols['name2'][idx_a]

        first_b = cols['first'][idx_b]
        last_b = cols['last'][idx_b]
        name2_b = cols['name2'][idx_b]

        # Combine last + name2 for full surname comparison
        last_full_a = f"{last_a} {name2_a}".strip() if name2_a else last_a
        last_full_b = f"{last_b} {name2_b}".strip() if name2_b else last_b

        # Use existing name comparison logic
        name_comp = compare_names_with_swap(first_a, last_full_a, first_b, last_full_b)

        # Normal orientation
        features['name_wratio_normal'] = name_comp['normal_score']
        features['first_wratio_normal'] = name_comp['normal_first']
        features['last_wratio_normal'] = name_comp['normal_last']

        # Swapped orientation
        features['name_wratio_swapped'] = name_comp['swapped_score']
        features['first_wratio_swapped'] = name_comp['swapped_first']
        features['last_wratio_swapped'] = name_comp['swapped_last']

        # Cologne phonetic matching
        try:
            from cologne_phonetics import encode as cologne_encode

            cologne_first_a = cologne_encode(first_a) if first_a else ''
            cologne_first_b = cologne_encode(first_b) if first_b else ''
            cologne_last_a = cologne_encode(last_a) if last_a else ''
            cologne_last_b = cologne_encode(last_b) if last_b else ''

            features['cologne_first_match'] = 1.0 if (
                cologne_first_a and cologne_first_b and cologne_first_a == cologne_first_b
            ) else 0.0
            features['cologne_last_match'] = 1.0 if (
                cologne_last_a and cologne_last_b and cologne_last_a == cologne_last_b
            ) else 0.0
        except ImportError:
            features['cologne_first_match'] = 0.0
            features['cologne_last_match'] = 0.0

        # Name2/Zweitname features
        features['name2_present_both'] = float(bool(name2_a) and bool(name2_b))

        # Check for zweitname conflict
        zweitname_ok = check_zweitname(name2_a, last_a, name2_b, last_b)
        features['name2_conflict'] = float(not zweitname_ok)

        return features

    def _extract_address_features(
        self,
        idx_a: int,
        idx_b: int,
        cols: Dict,
    ) -> Dict[str, float]:
        """Extract address similarity features."""
        features = {}

        # PLZ comparison
        plz_a = cols['plz4_used'][idx_a]
        plz_b = cols['plz4_used'][idx_b]

        features['plz_exact_match'] = float(plz_a == plz_b)
        features['plz_region_match'] = float(
            bool(plz_a) and bool(plz_b) and plz_a[:2] == plz_b[:2]
        )

        # House number comparison
        house_a = cols['house'][idx_a]
        house_b = cols['house'][idx_b]
        house_num_a = cols['house_num'][idx_a]
        house_num_b = cols['house_num'][idx_b]

        features['house_exact_match'] = float(house_a == house_b)

        # Street comparison
        street_a = cols['street'][idx_a]
        street_b = cols['street'][idx_b]
        features['street_wratio'] = fuzz.WRatio(street_a, street_b) / 100.0

        # Ort comparison
        ort_a = cols['ort'][idx_a]
        ort_b = cols['ort'][idx_b]
        features['ort_wratio'] = fuzz.ratio(ort_a, ort_b) / 100.0

        # Blocking key matches
        addr_key_a = cols['addr_key_building'][idx_a]
        addr_key_b = cols['addr_key_building'][idx_b]
        features['addr_key_match'] = float(addr_key_a == addr_key_b)

        # Street signature match (typo recovery)
        street_sig_a = cols.get('street_sig', [None] * len(cols['street']))[idx_a]
        street_sig_b = cols.get('street_sig', [None] * len(cols['street']))[idx_b]
        features['street_sig_match'] = float(
            bool(street_sig_a) and bool(street_sig_b) and street_sig_a == street_sig_b
        )

        # Composite address score (similar to existing scoring.py logic)
        plz_score = 1.0 if plz_a == plz_b else 0.0
        house_score = 1.0 if house_num_a == house_num_b else 0.0
        street_score = features['street_wratio']
        ort_score = features['ort_wratio']

        features['address_composite_score'] = (
            0.4 * plz_score +
            0.2 * house_score +
            0.2 * street_score +
            0.2 * ort_score
        )

        return features

    def _extract_date_features(
        self,
        idx_a: int,
        idx_b: int,
        cols: Dict,
    ) -> Dict[str, float]:
        """Extract date/birth data features."""
        features = {}

        dob_a = cols['dob_ymd'][idx_a]
        dob_b = cols['dob_ymd'][idx_b]
        yob_a = cols['yob'][idx_a]
        yob_b = cols['yob'][idx_b]

        # DOB exact match
        features['dob_exact_match'] = float(
            dob_a > 0 and dob_b > 0 and dob_a == dob_b
        )

        # YOB exact match
        features['yob_exact_match'] = float(
            yob_a > 0 and yob_b > 0 and yob_a == yob_b
        )

        # DOB quality indicators
        features['dob_both_present'] = float(dob_a > 0 and dob_b > 0)
        features['dob_one_missing'] = float(
            (dob_a > 0 and dob_b <= 0) or (dob_a <= 0 and dob_b > 0)
        )

        # YOB quality indicators
        features['yob_both_present'] = float(yob_a > 0 and yob_b > 0)
        features['yob_one_missing'] = float(
            (yob_a > 0 and yob_b <= 0) or (yob_a <= 0 and yob_b > 0)
        )

        return features

    def _extract_embedding_features(
        self,
        idx_a: int,
        idx_b: int,
    ) -> Dict[str, float]:
        """Extract embedding-based similarity features."""
        features = {}

        if self.embedding_store is None:
            return {
                'emb_cosine_similarity': 0.0,
                'emb_l2_distance': 0.0,
                'emb_dot_product': 0.0,
                'emb_manhattan_distance': 0.0,
            }

        # Get embeddings
        emb_a = self.embedding_store.lookup_by_index(idx_a)
        emb_b = self.embedding_store.lookup_by_index(idx_b)

        if emb_a is None or emb_b is None:
            return {
                'emb_cosine_similarity': 0.0,
                'emb_l2_distance': 0.0,
                'emb_dot_product': 0.0,
                'emb_manhattan_distance': 0.0,
            }

        # Cosine similarity (assumes normalized embeddings)
        features['emb_cosine_similarity'] = float(np.dot(emb_a, emb_b))

        # L2 distance (Euclidean)
        features['emb_l2_distance'] = float(np.linalg.norm(emb_a - emb_b))

        # Dot product (raw similarity)
        features['emb_dot_product'] = float(np.dot(emb_a, emb_b))

        # Manhattan distance (L1)
        features['emb_manhattan_distance'] = float(np.sum(np.abs(emb_a - emb_b)))

        return features

    def _extract_name_embedding_features(
        self,
        idx_a: int,
        idx_b: int,
    ) -> Dict[str, float]:
        """
        Extract name-only embedding similarity features.

        These features use embeddings generated only from name fields (no address),
        which is critical for proper entity matching. Address contamination in
        embeddings can lead to high similarity for different people at the same
        address.
        """
        features = {}

        if self.name_embedding_store is None:
            return {
                'name_emb_cosine_similarity': 0.0,
                'name_emb_l2_distance': 0.0,
                'name_emb_dot_product': 0.0,
                'name_emb_manhattan_distance': 0.0,
            }

        # Get name-only embeddings
        emb_a = self.name_embedding_store.lookup_by_index(idx_a)
        emb_b = self.name_embedding_store.lookup_by_index(idx_b)

        if emb_a is None or emb_b is None:
            return {
                'name_emb_cosine_similarity': 0.0,
                'name_emb_l2_distance': 0.0,
                'name_emb_dot_product': 0.0,
                'name_emb_manhattan_distance': 0.0,
            }

        # Cosine similarity (assumes normalized embeddings)
        features['name_emb_cosine_similarity'] = float(np.dot(emb_a, emb_b))

        # L2 distance (Euclidean)
        features['name_emb_l2_distance'] = float(np.linalg.norm(emb_a - emb_b))

        # Dot product (raw similarity)
        features['name_emb_dot_product'] = float(np.dot(emb_a, emb_b))

        # Manhattan distance (L1)
        features['name_emb_manhattan_distance'] = float(np.sum(np.abs(emb_a - emb_b)))

        return features

    def _extract_interaction_features(
        self,
        idx_a: int,
        idx_b: int,
        cols: Dict,
        name_features: Dict[str, float],
        addr_features: Dict[str, float],
    ) -> Dict[str, float]:
        """Extract interaction and derived features."""
        features = {}

        # Name × Address interaction
        name_score = max(
            name_features['name_wratio_normal'],
            name_features['name_wratio_swapped'],
        )
        addr_score = addr_features['address_composite_score']
        features['name_addr_interaction'] = name_score * addr_score

        # First word bonus (from existing logic)
        first_a = cols['first'][idx_a]
        first_b = cols['first'][idx_b]
        street_a = cols['street'][idx_a]
        street_b = cols['street'][idx_b]
        house_a = cols['house'][idx_a]
        house_b = cols['house'][idx_b]
        plz_a = cols['plz4_used'][idx_a]
        plz_b = cols['plz4_used'][idx_b]
        ort_a = cols['ort'][idx_a]
        ort_b = cols['ort'][idx_b]

        bonus = get_first_word_bonus(
            first_a, first_b,
            plz_a, plz_b,
            house_a, house_b,
            street_a, street_b,
            ort_a, ort_b,
        )
        features['first_word_bonus'] = bonus / 100.0  # Normalize to [0, 1]

        return features

    def extract_features_batch(
        self,
        pairs: list,
        cols: Dict,
        include_embeddings: bool = True,
    ) -> Tuple[np.ndarray, list]:
        """
        Extract features for a batch of pairs with vectorized embedding calculations.

        Args:
            pairs: List of (idx_a, idx_b) tuples
            cols: Dictionary of preprocessed columns
            include_embeddings: Whether to include embedding features

        Returns:
            Tuple of (feature_matrix, feature_names)
            - feature_matrix: numpy array of shape (n_pairs, n_features)
            - feature_names: list of feature names
        """
        n_pairs = len(pairs)
        if n_pairs == 0:
            return np.zeros((0, self.n_features), dtype=np.float32), self.FEATURE_NAMES

        feature_matrix = np.zeros((n_pairs, self.n_features), dtype=np.float32)

        # Pre-compute vectorized embedding features if available
        emb_features = None
        if include_embeddings and self.embedding_store is not None:
            emb_features = self._extract_embedding_features_batch(pairs)

        # Pre-compute vectorized name embedding features if available
        name_emb_features = None
        if include_embeddings and self.name_embedding_store is not None:
            name_emb_features = self._extract_name_embedding_features_batch(pairs)

        # Extract non-embedding features per pair (string ops can't be vectorized easily)
        for i, (idx_a, idx_b) in enumerate(pairs):
            # Name features
            name_features = self._extract_name_features(idx_a, idx_b, cols)

            # Address features
            addr_features = self._extract_address_features(idx_a, idx_b, cols)

            # Date features
            date_features = self._extract_date_features(idx_a, idx_b, cols)

            # Interaction features
            interaction_features = self._extract_interaction_features(
                idx_a, idx_b, cols, name_features, addr_features
            )

            # Combine all features for this pair
            all_features = {
                **name_features,
                **addr_features,
                **date_features,
                **interaction_features,
            }

            # Fill feature matrix row
            for j, feat_name in enumerate(self.FEATURE_NAMES):
                if feat_name.startswith('emb_') and not feat_name.startswith('name_emb_') and emb_features is not None:
                    # Use pre-computed vectorized full embedding feature
                    feature_matrix[i, j] = emb_features[feat_name][i]
                elif feat_name.startswith('name_emb_') and name_emb_features is not None:
                    # Use pre-computed vectorized name embedding feature
                    feature_matrix[i, j] = name_emb_features[feat_name][i]
                else:
                    feature_matrix[i, j] = all_features.get(feat_name, 0.0)

        return feature_matrix, self.FEATURE_NAMES

    def _extract_embedding_features_batch(
        self,
        pairs: list,
    ) -> Dict[str, np.ndarray]:
        """
        Extract embedding features for a batch of pairs using vectorized operations.

        This is significantly faster than per-pair extraction for large batches.

        Args:
            pairs: List of (idx_a, idx_b) tuples

        Returns:
            Dictionary mapping feature names to arrays of values
        """
        n_pairs = len(pairs)

        # Initialize output arrays
        cosine_sim = np.zeros(n_pairs, dtype=np.float32)
        l2_dist = np.zeros(n_pairs, dtype=np.float32)
        dot_prod = np.zeros(n_pairs, dtype=np.float32)
        manhattan_dist = np.zeros(n_pairs, dtype=np.float32)

        if self.embedding_store is None:
            return {
                'emb_cosine_similarity': cosine_sim,
                'emb_l2_distance': l2_dist,
                'emb_dot_product': dot_prod,
                'emb_manhattan_distance': manhattan_dist,
            }

        # Collect positions for batch lookup
        positions_a = []
        positions_b = []
        valid_indices = []

        for i, (idx_a, idx_b) in enumerate(pairs):
            pos_a = self.embedding_store.index_to_pos.get(idx_a)
            pos_b = self.embedding_store.index_to_pos.get(idx_b)

            if pos_a is not None and pos_b is not None:
                positions_a.append(pos_a)
                positions_b.append(pos_b)
                valid_indices.append(i)

        if not valid_indices:
            return {
                'emb_cosine_similarity': cosine_sim,
                'emb_l2_distance': l2_dist,
                'emb_dot_product': dot_prod,
                'emb_manhattan_distance': manhattan_dist,
            }

        # Batch lookup embeddings
        emb_a = self.embedding_store.lookup_batch(positions_a)  # (n_valid, dim)
        emb_b = self.embedding_store.lookup_batch(positions_b)  # (n_valid, dim)

        # Vectorized similarity calculations
        # Cosine similarity (assumes normalized embeddings)
        valid_cosine = np.sum(emb_a * emb_b, axis=1)

        # L2 distance
        diff = emb_a - emb_b
        valid_l2 = np.linalg.norm(diff, axis=1)

        # Dot product (same as cosine for normalized)
        valid_dot = valid_cosine

        # Manhattan distance
        valid_manhattan = np.sum(np.abs(diff), axis=1)

        # Fill results at valid indices
        for j, i in enumerate(valid_indices):
            cosine_sim[i] = valid_cosine[j]
            l2_dist[i] = valid_l2[j]
            dot_prod[i] = valid_dot[j]
            manhattan_dist[i] = valid_manhattan[j]

        return {
            'emb_cosine_similarity': cosine_sim,
            'emb_l2_distance': l2_dist,
            'emb_dot_product': dot_prod,
            'emb_manhattan_distance': manhattan_dist,
        }

    def _extract_name_embedding_features_batch(
        self,
        pairs: list,
    ) -> Dict[str, np.ndarray]:
        """
        Extract name-only embedding features for a batch using vectorized operations.

        This uses embeddings generated only from name fields (no address),
        which is critical for proper entity matching.

        Args:
            pairs: List of (idx_a, idx_b) tuples

        Returns:
            Dictionary mapping feature names to arrays of values
        """
        n_pairs = len(pairs)

        # Initialize output arrays
        cosine_sim = np.zeros(n_pairs, dtype=np.float32)
        l2_dist = np.zeros(n_pairs, dtype=np.float32)
        dot_prod = np.zeros(n_pairs, dtype=np.float32)
        manhattan_dist = np.zeros(n_pairs, dtype=np.float32)

        if self.name_embedding_store is None:
            return {
                'name_emb_cosine_similarity': cosine_sim,
                'name_emb_l2_distance': l2_dist,
                'name_emb_dot_product': dot_prod,
                'name_emb_manhattan_distance': manhattan_dist,
            }

        # Collect positions for batch lookup
        positions_a = []
        positions_b = []
        valid_indices = []

        for i, (idx_a, idx_b) in enumerate(pairs):
            pos_a = self.name_embedding_store.index_to_pos.get(idx_a)
            pos_b = self.name_embedding_store.index_to_pos.get(idx_b)

            if pos_a is not None and pos_b is not None:
                positions_a.append(pos_a)
                positions_b.append(pos_b)
                valid_indices.append(i)

        if not valid_indices:
            return {
                'name_emb_cosine_similarity': cosine_sim,
                'name_emb_l2_distance': l2_dist,
                'name_emb_dot_product': dot_prod,
                'name_emb_manhattan_distance': manhattan_dist,
            }

        # Batch lookup embeddings
        emb_a = self.name_embedding_store.lookup_batch(positions_a)
        emb_b = self.name_embedding_store.lookup_batch(positions_b)

        # Vectorized similarity calculations
        # Cosine similarity (assumes normalized embeddings)
        valid_cosine = np.sum(emb_a * emb_b, axis=1)

        # L2 distance
        diff = emb_a - emb_b
        valid_l2 = np.linalg.norm(diff, axis=1)

        # Dot product (same as cosine for normalized)
        valid_dot = valid_cosine

        # Manhattan distance
        valid_manhattan = np.sum(np.abs(diff), axis=1)

        # Fill results at valid indices
        for j, i in enumerate(valid_indices):
            cosine_sim[i] = valid_cosine[j]
            l2_dist[i] = valid_l2[j]
            dot_prod[i] = valid_dot[j]
            manhattan_dist[i] = valid_manhattan[j]

        return {
            'name_emb_cosine_similarity': cosine_sim,
            'name_emb_l2_distance': l2_dist,
            'name_emb_dot_product': dot_prod,
            'name_emb_manhattan_distance': manhattan_dist,
        }

    def check_business_rule_violations(
        self,
        idx_a: int,
        idx_b: int,
        cols: Dict,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if pair violates hard business rules.

        Returns:
            Tuple of (is_valid, reason)
            - is_valid: True if pair passes all hard gates
            - reason: String describing violation if is_valid=False
        """
        dob_a = cols['dob_ymd'][idx_a]
        dob_b = cols['dob_ymd'][idx_b]
        yob_a = cols['yob'][idx_a]
        yob_b = cols['yob'][idx_b]

        # Hard gate 1: DOB mismatch
        if dob_a > 0 and dob_b > 0 and dob_a != dob_b:
            return False, "dob_mismatch"

        # Hard gate 2: YOB mismatch
        if yob_a > 0 and yob_b > 0 and yob_a != yob_b:
            return False, "yob_mismatch"

        # Hard gate 3: Zweitname conflict
        name2_a = cols['name2'][idx_a]
        name2_b = cols['name2'][idx_b]
        last_a = cols['last'][idx_a]
        last_b = cols['last'][idx_b]

        if not check_zweitname(name2_a, last_a, name2_b, last_b):
            return False, "zweitname_conflict"

        return True, None


def get_feature_importance_names():
    """
    Get human-readable feature names for model interpretation.

    Returns:
        Dictionary mapping feature names to descriptions
    """
    return {
        'name_wratio_normal': 'Name similarity (normal order)',
        'name_wratio_swapped': 'Name similarity (swapped order)',
        'first_wratio_normal': 'First name similarity (normal)',
        'first_wratio_swapped': 'First name similarity (swapped)',
        'last_wratio_normal': 'Last name similarity (normal)',
        'last_wratio_swapped': 'Last name similarity (swapped)',
        'cologne_first_match': 'First name phonetic match (Cologne)',
        'cologne_last_match': 'Last name phonetic match (Cologne)',
        'name2_present_both': 'Both have second name',
        'name2_conflict': 'Second name conflict detected',
        'plz_exact_match': 'Postal code exact match',
        'plz_region_match': 'Postal code region match',
        'house_exact_match': 'House number exact match',
        'street_wratio': 'Street name similarity',
        'ort_wratio': 'City/locality similarity',
        'addr_key_match': 'Address blocking key match',
        'street_sig_match': 'Street signature match (typo recovery)',
        'address_composite_score': 'Composite address score',
        'dob_exact_match': 'Date of birth exact match',
        'yob_exact_match': 'Year of birth exact match',
        'dob_both_present': 'Both have date of birth',
        'dob_one_missing': 'One date of birth missing',
        'yob_both_present': 'Both have year of birth',
        'yob_one_missing': 'One year of birth missing',
        'emb_cosine_similarity': 'Full embedding cosine similarity (name+addr)',
        'emb_l2_distance': 'Full embedding Euclidean distance',
        'emb_dot_product': 'Full embedding dot product',
        'emb_manhattan_distance': 'Full embedding Manhattan distance',
        'name_emb_cosine_similarity': 'Name-only embedding cosine similarity',
        'name_emb_l2_distance': 'Name-only embedding Euclidean distance',
        'name_emb_dot_product': 'Name-only embedding dot product',
        'name_emb_manhattan_distance': 'Name-only embedding Manhattan distance',
        'name_addr_interaction': 'Name × Address interaction',
        'first_word_bonus': 'First word match bonus',
    }
