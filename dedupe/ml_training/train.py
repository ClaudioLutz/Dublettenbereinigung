"""
Training orchestration for ML-based entity matching.

Combines silver label generation, feature extraction, model training,
and calibration into a complete training pipeline.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from dedupe.io import get_engine, read_sql_df
from dedupe.ml.calibration import ModelCalibrator
from dedupe.ml.features import FeatureExtractor
from dedupe.ml.model import EntityMatchingModel
from dedupe.ml_training.silver_labels import SilverLabelGenerator
from dedupe.preprocess import preprocess

logger = logging.getLogger(__name__)


class TrainingPipeline:
    """
    Complete training pipeline for entity matching ML model.

    Orchestrates:
    1. Silver label generation from rule-based results
    2. Feature extraction from labeled pairs
    3. LightGBM model training with cross-validation
    4. Isotonic regression calibration
    5. Model and calibrator saving
    """

    def __init__(
        self,
        embedding_store=None,
        random_state: int = 42,
    ):
        """
        Initialize training pipeline.

        Args:
            embedding_store: Optional EmbeddingStore for embedding features
            random_state: Random seed for reproducibility
        """
        self.embedding_store = embedding_store
        self.random_state = random_state

        self.feature_extractor = FeatureExtractor(embedding_store=embedding_store)
        self.model = None
        self.calibrator = None

    def load_and_prepare_data(
        self,
        query: str,
        db_server: str,
        db_database: str,
        silver_labels_df: pd.DataFrame,
        chunksize: int = 200_000,
    ) -> Tuple[np.ndarray, np.ndarray, list, Dict]:
        """
        Load data and extract features for labeled pairs.

        Args:
            query: SQL query to load data
            db_server: Database server
            db_database: Database name
            silver_labels_df: DataFrame with silver labels (idx_a, idx_b, label)
            chunksize: Chunk size for loading data

        Returns:
            Tuple of (X, y, feature_names, cols_dict)
        """
        logger.info("Loading and preprocessing data...")

        # Connect to database
        engine = get_engine(db_server, db_database)

        # Load all data (for feature extraction)
        # In production, this could be optimized to only load required indices
        all_data = []
        for chunk in read_sql_df(engine, query, chunksize=chunksize):
            all_data.append(chunk)

        df = pd.concat(all_data, ignore_index=True)
        logger.info(f"Loaded {len(df)} records")

        # Preprocess
        cols = preprocess(df, address_normalizer=None)

        logger.info("Extracting features for labeled pairs...")

        # Extract features for all labeled pairs
        pairs = list(zip(silver_labels_df['idx_a'], silver_labels_df['idx_b']))
        labels = silver_labels_df['label'].values

        # Extract features in batches for efficiency
        X, feature_names = self.feature_extractor.extract_features_batch(
            pairs, cols, include_embeddings=(self.embedding_store is not None)
        )

        logger.info(f"Extracted {X.shape[1]} features for {len(pairs)} pairs")

        return X, labels, feature_names, cols

    def train_model(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list,
        test_size: float = 0.2,
        use_cv: bool = False,
        n_cv_folds: int = 5,
    ) -> Dict[str, float]:
        """
        Train LightGBM model.

        Args:
            X: Feature matrix
            y: Labels
            feature_names: List of feature names
            test_size: Fraction of data for testing
            use_cv: Whether to use cross-validation
            n_cv_folds: Number of CV folds

        Returns:
            Dictionary of training metrics
        """
        logger.info("Training LightGBM model...")

        # Split into train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.random_state, stratify=y
        )

        logger.info(f"Train size: {len(y_train)}, Test size: {len(y_test)}")

        # Initialize model
        self.model = EntityMatchingModel()

        # Train with cross-validation or simple train/val split
        if use_cv:
            cv_scores = self.model.cross_validate(
                X_train, y_train, feature_names=feature_names, n_splits=n_cv_folds
            )

            # Retrain on full training set for final model
            logger.info("Retraining on full training set...")
            metrics = self.model.train(
                X_train, y_train, X_test, y_test, feature_names=feature_names
            )
        else:
            # Simple train/validation split
            X_train_split, X_val, y_train_split, y_val = train_test_split(
                X_train, y_train, test_size=0.2, random_state=self.random_state, stratify=y_train
            )

            metrics = self.model.train(
                X_train_split, y_train_split, X_val, y_val, feature_names=feature_names
            )

        # Final test set evaluation
        y_test_pred = self.model.predict_proba(X_test)
        from sklearn.metrics import roc_auc_score, accuracy_score

        metrics['test_auc'] = roc_auc_score(y_test, y_test_pred)
        metrics['test_accuracy'] = accuracy_score(y_test, y_test_pred > 0.5)

        logger.info(f"Test AUC: {metrics['test_auc']:.4f}")
        logger.info(f"Test Accuracy: {metrics['test_accuracy']:.4f}")

        return metrics

    def calibrate_model(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ):
        """
        Calibrate model using isotonic regression.

        Args:
            X_val: Validation features
            y_val: Validation labels
        """
        logger.info("Calibrating model...")

        # Get uncalibrated predictions
        y_val_pred = self.model.predict_proba(X_val)

        # Fit calibrator
        self.calibrator = ModelCalibrator()
        self.calibrator.fit(y_val_pred, y_val)

    def save_models(
        self,
        output_dir: str,
        version: str = 'v1',
    ):
        """
        Save trained model and calibrator.

        Args:
            output_dir: Directory to save models
            version: Version identifier
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save model
        self.model.save(output_path / 'lightgbm', version=version)

        # Save calibrator
        if self.calibrator:
            calibrator_path = output_path / 'lightgbm' / f'calibrator_{version}.pkl'
            self.calibrator.save(calibrator_path)

        logger.info(f"Models saved to {output_path}")

    def run_complete_pipeline(
        self,
        results_path: str,
        query_path: str,
        db_server: str,
        db_database: str,
        output_dir: str,
        positive_threshold: float = 95.0,
        negative_ratio: float = 2.5,
        use_cv: bool = False,
        version: str = 'v1',
    ) -> Dict[str, float]:
        """
        Run complete training pipeline end-to-end.

        Args:
            results_path: Path to rule-based results CSV
            query_path: Path to SQL query file
            db_server: Database server
            db_database: Database name
            output_dir: Output directory for models
            positive_threshold: Confidence threshold for positive labels
            negative_ratio: Ratio of negatives to positives
            use_cv: Whether to use cross-validation
            version: Model version

        Returns:
            Dictionary of final metrics
        """
        start_time = time.time()

        logger.info("=" * 80)
        logger.info("ML TRAINING PIPELINE")
        logger.info("=" * 80)

        # Step 1: Generate silver labels
        logger.info("Step 1/5: Generating silver labels...")
        label_generator = SilverLabelGenerator(
            positive_confidence_threshold=positive_threshold,
            negative_ratio=negative_ratio,
            hard_negative_strategy='mixed',
        )

        _, _, silver_labels_df = label_generator.generate_silver_labels(
            results_path=results_path,
            output_path=None,  # Don't save intermediate file
        )

        # Step 2: Load data and extract features
        logger.info("Step 2/5: Loading data and extracting features...")
        with open(query_path, 'r', encoding='utf-8') as f:
            query = f.read()

        X, y, feature_names, cols = self.load_and_prepare_data(
            query, db_server, db_database, silver_labels_df
        )

        # Step 3: Train model
        logger.info("Step 3/5: Training model...")
        metrics = self.train_model(X, y, feature_names, use_cv=use_cv)

        # Step 4: Calibrate model
        logger.info("Step 4/5: Calibrating model...")
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=self.random_state, stratify=y
        )
        self.calibrate_model(X_val, y_val)

        # Step 5: Save models
        logger.info("Step 5/5: Saving models...")
        self.save_models(output_dir, version=version)

        elapsed_time = time.time() - start_time

        logger.info("=" * 80)
        logger.info("TRAINING COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total time: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
        logger.info(f"Output directory: {output_dir}")
        logger.info("=" * 80)

        return metrics
