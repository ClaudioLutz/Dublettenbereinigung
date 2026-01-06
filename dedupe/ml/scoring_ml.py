"""
ML-based scoring for entity matching (Phase 4 integration).

Provides MLScorer class that acts as a drop-in replacement for the
rule-based score_pair function while preserving business rule gates.
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from dedupe.ml.calibration import ModelCalibrator
from dedupe.ml.features import FeatureExtractor
from dedupe.ml.model import EntityMatchingModel
from dedupe.scoring import MatchResult

logger = logging.getLogger(__name__)


class MLScorer:
    """
    ML-based entity matching scorer with business rule gates.

    This class integrates ML scoring into the existing pipeline while:
    - Preserving hard business rule gates (DOB mismatch, Zweitname conflicts)
    - Enforcing minimum name similarity threshold (prevents same-address different-person matches)
    - Using calibrated probabilities for confidence scores
    - Falling back to rule-based scoring on errors
    - Maintaining backward compatibility with existing output format
    """

    # Default minimum name similarity threshold (0-1 scale)
    # Pairs with name similarity below this are rejected as non-duplicates
    DEFAULT_MIN_NAME_SIMILARITY = 0.50

    def __init__(
        self,
        model: EntityMatchingModel,
        calibrator: Optional[ModelCalibrator] = None,
        embedding_store=None,
        name_embedding_store=None,
        enable_business_rules: bool = True,
        fallback_to_rules: bool = True,
        use_gpu: bool = False,
        min_name_similarity: float = DEFAULT_MIN_NAME_SIMILARITY,
    ):
        """
        Initialize ML scorer.

        Args:
            model: Trained EntityMatchingModel
            calibrator: Optional ModelCalibrator for calibrated probabilities
            embedding_store: Optional EmbeddingStore for full embedding features (name+address)
            name_embedding_store: Optional EmbeddingStore for name-only embedding features.
                                  Critical for proper entity matching to avoid address contamination.
            enable_business_rules: Whether to apply hard business rule gates
            fallback_to_rules: Whether to fall back to rule-based scoring on errors
            use_gpu: Whether to use GPU for model inference (requires cuML)
            min_name_similarity: Minimum name similarity threshold (0-1).
                                 Pairs below this are rejected as non-duplicates.
                                 This prevents same-address different-person matches.
                                 Default: 0.50 (50% similarity required)
        """
        self.model = model
        self.calibrator = calibrator
        self.embedding_store = embedding_store
        self.name_embedding_store = name_embedding_store
        self.enable_business_rules = enable_business_rules
        self.fallback_to_rules = fallback_to_rules
        self.use_gpu = use_gpu
        self.min_name_similarity = min_name_similarity

        self.feature_extractor = FeatureExtractor(
            embedding_store=embedding_store,
            name_embedding_store=name_embedding_store,
        )

        self.ml_predictions = 0
        self.rule_rejections = 0
        self.name_similarity_rejections = 0  # Track name similarity gate rejections
        self.errors = 0

        # Initialize GPU if requested
        if use_gpu:
            gpu_ok = self.model.load_for_gpu_inference()
            if not gpu_ok:
                logger.warning("GPU initialization failed, falling back to CPU")
                self.use_gpu = False

        if min_name_similarity > 0:
            logger.info(f"Name similarity gate enabled: minimum {min_name_similarity*100:.0f}% required")

    def score_pair(
        self,
        i: int,
        j: int,
        cols: Dict,
        fuzzy_threshold: float = 0.80,
    ) -> Optional[MatchResult]:
        """
        Score a pair using ML model (with business rule gates).

        This method is designed to be a drop-in replacement for
        dedupe.scoring.score_pair while using ML for scoring.

        Args:
            i: Index of first record
            j: Index of second record
            cols: Dictionary of preprocessed columns
            fuzzy_threshold: Not used for ML (kept for compatibility)

        Returns:
            MatchResult if pair passes gates and has features, None otherwise
        """
        try:
            # Step 1: Apply business rule gates (if enabled)
            if self.enable_business_rules:
                is_valid, reason = self.feature_extractor.check_business_rule_violations(
                    i, j, cols
                )

                if not is_valid:
                    # Hard rejection by business rules
                    self.rule_rejections += 1
                    logger.debug(f"Pair ({i}, {j}) rejected by business rule: {reason}")
                    return None

            # Step 2: Extract features
            features = self.feature_extractor.extract_features(
                i, j, cols, include_embeddings=(self.embedding_store is not None)
            )

            # Step 3: Apply name similarity gate (prevents same-address different-person)
            name_sim = max(
                features.get('name_wratio_normal', 0),
                features.get('name_wratio_swapped', 0)
            )
            if self.min_name_similarity > 0 and name_sim < self.min_name_similarity:
                self.name_similarity_rejections += 1
                logger.debug(
                    f"Pair ({i}, {j}) rejected by name similarity gate: "
                    f"{name_sim:.2f} < {self.min_name_similarity:.2f}"
                )
                return None

            # Step 4: Convert to feature vector
            feature_vector = np.array([
                features.get(fname, 0.0)
                for fname in self.feature_extractor.FEATURE_NAMES
            ], dtype=np.float32).reshape(1, -1)

            # Step 5: Predict with ML model
            prob_raw = self.model.predict_proba(feature_vector)[0]

            # Step 6: Apply calibration if available
            if self.calibrator is not None:
                prob_calibrated = self.calibrator.transform(np.array([prob_raw]))[0]
            else:
                prob_calibrated = prob_raw

            # Step 7: Convert to confidence score (0-100)
            confidence = float(prob_calibrated * 100.0)

            # Step 8: Determine match type based on key features
            match_type = self._classify_match_type(features, prob_calibrated)

            # Step 9: Determine if swapped (for compatibility with existing output)
            is_swapped = features['name_wratio_swapped'] > features['name_wratio_normal']

            # Step 10: Extract component scores for compatibility
            name_score = max(
                features['name_wratio_normal'],
                features['name_wratio_swapped']
            ) * 100.0

            addr_score = features['address_composite_score'] * 100.0

            self.ml_predictions += 1

            # Return MatchResult (compatible with existing pipeline)
            return MatchResult(
                i=i,
                j=j,
                score=confidence,
                name_score=name_score,
                addr_score=addr_score,
                reason=match_type,
                is_swapped=is_swapped,
            )

        except Exception as e:
            self.errors += 1
            logger.warning(f"ML scoring failed for pair ({i}, {j}): {e}")

            # Fallback to rule-based scoring
            if self.fallback_to_rules:
                from dedupe.scoring import score_pair
                return score_pair(i, j, cols, fuzzy_threshold)
            else:
                return None

    def score_batch(
        self,
        pairs: List[Tuple[int, int]],
        cols: Dict,
        fuzzy_threshold: float = 0.80,
    ) -> List[Optional[MatchResult]]:
        """
        Score multiple pairs using batch ML inference.

        This method processes pairs in batch for significantly better performance
        compared to calling score_pair() individually.

        Args:
            pairs: List of (i, j) tuples representing record pairs
            cols: Dictionary of preprocessed columns
            fuzzy_threshold: Not used for ML (kept for compatibility)

        Returns:
            List of MatchResult objects (None for rejected pairs).
            The list maintains the same order as input pairs.
        """
        if not pairs:
            return []

        n_pairs = len(pairs)
        results: List[Optional[MatchResult]] = [None] * n_pairs

        # Step 1: Apply business rule gates (filter invalid pairs)
        valid_pairs: List[Tuple[int, int]] = []
        valid_indices: List[int] = []

        for idx, (i, j) in enumerate(pairs):
            if self.enable_business_rules:
                is_valid, reason = self.feature_extractor.check_business_rule_violations(
                    i, j, cols
                )
                if not is_valid:
                    self.rule_rejections += 1
                    continue

            valid_pairs.append((i, j))
            valid_indices.append(idx)

        if not valid_pairs:
            return results

        try:
            # Step 2: Batch feature extraction
            feature_matrix, feature_names = self.feature_extractor.extract_features_batch(
                valid_pairs,
                cols,
                include_embeddings=(self.embedding_store is not None),
            )

            # Step 3: Apply name similarity gate (filter out low name similarity pairs)
            # This prevents same-address different-person matches from being considered
            name_sim_passed_pairs = []
            name_sim_passed_indices = []
            name_sim_passed_features = []

            # Get indices of name similarity features
            name_wratio_normal_idx = feature_names.index('name_wratio_normal') if 'name_wratio_normal' in feature_names else -1
            name_wratio_swapped_idx = feature_names.index('name_wratio_swapped') if 'name_wratio_swapped' in feature_names else -1

            for batch_idx, (i, j) in enumerate(valid_pairs):
                # Get name similarity for this pair
                name_sim_normal = feature_matrix[batch_idx, name_wratio_normal_idx] if name_wratio_normal_idx >= 0 else 0
                name_sim_swapped = feature_matrix[batch_idx, name_wratio_swapped_idx] if name_wratio_swapped_idx >= 0 else 0
                name_sim = max(name_sim_normal, name_sim_swapped)

                if self.min_name_similarity > 0 and name_sim < self.min_name_similarity:
                    self.name_similarity_rejections += 1
                    continue

                name_sim_passed_pairs.append((i, j))
                name_sim_passed_indices.append(valid_indices[batch_idx])
                name_sim_passed_features.append(batch_idx)

            if not name_sim_passed_pairs:
                return results

            # Filter feature matrix to only include pairs that passed name similarity gate
            filtered_feature_matrix = feature_matrix[name_sim_passed_features]

            # Step 4: Batch model prediction (GPU or CPU)
            if self.use_gpu and self.model.is_gpu_available():
                probs_raw = self.model.predict_proba_gpu(filtered_feature_matrix)
            else:
                probs_raw = self.model.predict_proba(filtered_feature_matrix)

            # Step 5: Batch calibration (if available)
            if self.calibrator is not None:
                probs_calibrated = self.calibrator.transform(probs_raw)
            else:
                probs_calibrated = probs_raw

            # Step 6: Build MatchResult objects for each pair that passed all gates
            for filtered_idx, (i, j) in enumerate(name_sim_passed_pairs):
                orig_idx = name_sim_passed_indices[filtered_idx]
                orig_feature_idx = name_sim_passed_features[filtered_idx]
                prob = probs_calibrated[filtered_idx]
                confidence = float(prob * 100.0)

                # Extract individual features for this pair (from pre-computed matrix)
                features = {}
                for feat_idx, feat_name in enumerate(feature_names):
                    features[feat_name] = float(feature_matrix[orig_feature_idx, feat_idx])

                match_type = self._classify_match_type(features, prob)
                is_swapped = features.get('name_wratio_swapped', 0) > features.get('name_wratio_normal', 0)

                name_score = max(
                    features.get('name_wratio_normal', 0),
                    features.get('name_wratio_swapped', 0)
                ) * 100.0

                addr_score = features.get('address_composite_score', 0) * 100.0

                results[orig_idx] = MatchResult(
                    i=i,
                    j=j,
                    score=confidence,
                    name_score=name_score,
                    addr_score=addr_score,
                    reason=match_type,
                    is_swapped=is_swapped,
                )

                self.ml_predictions += 1

        except Exception as e:
            self.errors += len(valid_pairs)
            logger.warning(f"Batch ML scoring failed for {len(valid_pairs)} pairs: {e}")

            # Fallback to per-pair rule-based scoring
            if self.fallback_to_rules:
                from dedupe.scoring import score_pair as rule_score_pair
                for batch_idx, (i, j) in enumerate(valid_pairs):
                    orig_idx = valid_indices[batch_idx]
                    try:
                        results[orig_idx] = rule_score_pair(i, j, cols, fuzzy_threshold)
                    except Exception:
                        pass

        return results

    def _classify_match_type(self, features: Dict[str, float], prob: float) -> str:
        """
        Classify match type based on features and probability.

        This provides interpretable match types similar to the rule-based system.

        Args:
            features: Feature dictionary
            prob: Calibrated match probability

        Returns:
            Match type string
        """
        # High confidence matches
        if prob >= 0.95:
            if features['dob_exact_match'] > 0.5 and features['name_wratio_normal'] > 0.95:
                return 'ml_high_confidence_exact'
            elif features['address_composite_score'] > 0.9:
                return 'ml_high_confidence_address'
            else:
                return 'ml_high_confidence'

        # Medium confidence matches
        elif prob >= 0.70:
            if features['emb_cosine_similarity'] > 0.85:
                return 'ml_medium_confidence_semantic'
            elif features['cologne_first_match'] > 0.5 and features['cologne_last_match'] > 0.5:
                return 'ml_medium_confidence_phonetic'
            else:
                return 'ml_medium_confidence'

        # Low confidence matches
        else:
            return 'ml_low_confidence'

    def get_statistics(self) -> Dict:
        """
        Get scoring statistics.

        Returns:
            Dictionary with prediction counts and GPU status
        """
        gpu_backend = None
        if hasattr(self.model, 'get_gpu_backend'):
            gpu_backend = self.model.get_gpu_backend()

        total = (
            self.ml_predictions +
            self.rule_rejections +
            self.name_similarity_rejections +
            self.errors
        )

        return {
            'ml_predictions': self.ml_predictions,
            'rule_rejections': self.rule_rejections,
            'name_similarity_rejections': self.name_similarity_rejections,
            'errors': self.errors,
            'total': total,
            'min_name_similarity': self.min_name_similarity,
            'gpu_enabled': self.use_gpu,
            'gpu_available': self.model.is_gpu_available() if hasattr(self.model, 'is_gpu_available') else False,
            'gpu_backend': gpu_backend,
        }

    @classmethod
    def load_from_directory(
        cls,
        model_dir: str,
        version: str = 'v1',
        embedding_store=None,
        name_embedding_store=None,
        use_gpu: bool = False,
        min_name_similarity: float = DEFAULT_MIN_NAME_SIMILARITY,
    ) -> 'MLScorer':
        """
        Load ML scorer from saved models.

        Args:
            model_dir: Directory containing saved models
            version: Model version to load
            embedding_store: Optional EmbeddingStore for full embeddings (name+address)
            name_embedding_store: Optional EmbeddingStore for name-only embeddings.
                                  Critical for proper entity matching.
            use_gpu: Whether to use GPU for inference (requires cuML)
            min_name_similarity: Minimum name similarity threshold (0-1).
                                 Default: 0.50 (50% similarity required)

        Returns:
            MLScorer instance
        """
        from pathlib import Path

        model_dir = Path(model_dir)

        # Load LightGBM model
        model_path = model_dir / 'lightgbm' / f'matcher_{version}.txt'
        metadata_path = model_dir / 'lightgbm' / f'matcher_{version}_metadata.json'

        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        model = EntityMatchingModel.load(str(model_path), str(metadata_path))
        logger.info(f"Loaded model from {model_path}")

        # Load calibrator
        calibrator = None
        calibrator_path = model_dir / 'lightgbm' / f'calibrator_{version}.pkl'
        if calibrator_path.exists():
            try:
                calibrator = ModelCalibrator.load(str(calibrator_path))
                logger.info(f"Loaded calibrator from {calibrator_path}")
            except Exception as e:
                logger.warning(f"Failed to load calibrator: {e}")

        return cls(
            model=model,
            calibrator=calibrator,
            embedding_store=embedding_store,
            name_embedding_store=name_embedding_store,
            use_gpu=use_gpu,
            min_name_similarity=min_name_similarity,
        )
