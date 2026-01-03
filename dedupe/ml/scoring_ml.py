"""
ML-based scoring for entity matching (Phase 4 integration).

Provides MLScorer class that acts as a drop-in replacement for the
rule-based score_pair function while preserving business rule gates.
"""

import logging
from typing import Dict, Optional

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
    - Using calibrated probabilities for confidence scores
    - Falling back to rule-based scoring on errors
    - Maintaining backward compatibility with existing output format
    """

    def __init__(
        self,
        model: EntityMatchingModel,
        calibrator: Optional[ModelCalibrator] = None,
        embedding_store=None,
        enable_business_rules: bool = True,
        fallback_to_rules: bool = True,
    ):
        """
        Initialize ML scorer.

        Args:
            model: Trained EntityMatchingModel
            calibrator: Optional ModelCalibrator for calibrated probabilities
            embedding_store: Optional EmbeddingStore for embedding features
            enable_business_rules: Whether to apply hard business rule gates
            fallback_to_rules: Whether to fall back to rule-based scoring on errors
        """
        self.model = model
        self.calibrator = calibrator
        self.embedding_store = embedding_store
        self.enable_business_rules = enable_business_rules
        self.fallback_to_rules = fallback_to_rules

        self.feature_extractor = FeatureExtractor(embedding_store=embedding_store)

        self.ml_predictions = 0
        self.rule_rejections = 0
        self.errors = 0

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

            # Step 3: Convert to feature vector
            feature_vector = np.array([
                features.get(fname, 0.0)
                for fname in self.feature_extractor.FEATURE_NAMES
            ], dtype=np.float32).reshape(1, -1)

            # Step 4: Predict with ML model
            prob_raw = self.model.predict_proba(feature_vector)[0]

            # Step 5: Apply calibration if available
            if self.calibrator is not None:
                prob_calibrated = self.calibrator.transform(np.array([prob_raw]))[0]
            else:
                prob_calibrated = prob_raw

            # Step 6: Convert to confidence score (0-100)
            confidence = float(prob_calibrated * 100.0)

            # Step 7: Determine match type based on key features
            match_type = self._classify_match_type(features, prob_calibrated)

            # Step 8: Determine if swapped (for compatibility with existing output)
            is_swapped = features['name_wratio_swapped'] > features['name_wratio_normal']

            # Step 9: Extract component scores for compatibility
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

    def get_statistics(self) -> Dict[str, int]:
        """
        Get scoring statistics.

        Returns:
            Dictionary with prediction counts
        """
        return {
            'ml_predictions': self.ml_predictions,
            'rule_rejections': self.rule_rejections,
            'errors': self.errors,
            'total': self.ml_predictions + self.rule_rejections + self.errors,
        }

    @classmethod
    def load_from_directory(
        cls,
        model_dir: str,
        version: str = 'v1',
        embedding_store=None,
    ) -> 'MLScorer':
        """
        Load ML scorer from saved models.

        Args:
            model_dir: Directory containing saved models
            version: Model version to load
            embedding_store: Optional EmbeddingStore

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
        )
