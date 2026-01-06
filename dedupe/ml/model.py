"""
LightGBM model wrapper for entity matching.

Provides a clean interface for training, predicting, and saving/loading
LightGBM models with monotonic constraints and precision-focused parameters.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import lightgbm as lgb
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

logger = logging.getLogger(__name__)


# Precision-focused LightGBM parameters
DEFAULT_PARAMS = {
    'objective': 'binary',
    'metric': ['auc', 'binary_logloss'],
    'boosting_type': 'gbdt',
    'num_leaves': 31,
    'learning_rate': 0.05,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'max_depth': 6,
    'min_data_in_leaf': 100,
    'lambda_l1': 0.1,
    'lambda_l2': 0.1,
    'verbose': -1,
}


class EntityMatchingModel:
    """
    LightGBM-based entity matching model with monotonic constraints.

    This model is optimized for precision-focused entity matching with:
    - Monotonic constraints (higher similarity → higher match probability)
    - Class imbalance handling
    - Cross-validation
    - Feature importance tracking
    """

    def __init__(
        self,
        params: Optional[Dict] = None,
        monotone_constraints: Optional[List[int]] = None,
        n_estimators: int = 500,
        early_stopping_rounds: int = 50,
    ):
        """
        Initialize entity matching model.

        Args:
            params: LightGBM parameters (uses defaults if None)
            monotone_constraints: List of constraints per feature
                                 (1=increasing, -1=decreasing, 0=no constraint)
            n_estimators: Number of boosting rounds
            early_stopping_rounds: Stop if no improvement for N rounds
        """
        self.params = params or DEFAULT_PARAMS.copy()
        self.monotone_constraints = monotone_constraints
        self.n_estimators = n_estimators
        self.early_stopping_rounds = early_stopping_rounds

        self.model = None
        self.feature_names = None
        self.best_iteration = None
        self.cv_scores = []

        # Thread lock for GPU inference (cuML is not thread-safe)
        self._gpu_lock = threading.Lock()

    def _get_monotone_constraints(self, feature_names: List[str]) -> List[int]:
        """
        Get monotonic constraints based on feature names.

        Returns list of constraints: 1 (increasing), -1 (decreasing), 0 (none)
        """
        if self.monotone_constraints is not None:
            return self.monotone_constraints

        # Default constraints based on feature semantics
        constraints = []

        for feat in feature_names:
            if any(keyword in feat for keyword in [
                'wratio', 'similarity', 'match', 'bonus', 'composite', 'interaction',
                'cosine', 'dot_product', 'both_present',
            ]):
                # Higher is better → should increase match probability
                constraints.append(1)
            elif any(keyword in feat for keyword in [
                'distance', 'conflict', 'missing', 'mismatch',
            ]):
                # Higher is worse → should decrease match probability
                constraints.append(-1)
            else:
                # No constraint
                constraints.append(0)

        logger.info(f"Monotonic constraints: {sum(c == 1 for c in constraints)} increasing, "
                   f"{sum(c == -1 for c in constraints)} decreasing, "
                   f"{sum(c == 0 for c in constraints)} unconstrained")

        return constraints

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        categorical_features: Optional[List[int]] = None,
    ) -> Dict[str, float]:
        """
        Train the model.

        Args:
            X_train: Training features (n_samples, n_features)
            y_train: Training labels (n_samples,)
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
            feature_names: List of feature names
            categorical_features: Indices of categorical features

        Returns:
            Dictionary of training metrics
        """
        self.feature_names = feature_names

        # Calculate class weights for imbalance
        n_pos = np.sum(y_train == 1)
        n_neg = np.sum(y_train == 0)
        scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

        logger.info(f"Class distribution: {n_pos} positives, {n_neg} negatives")
        logger.info(f"Scale pos weight: {scale_pos_weight:.2f}")

        # Update params with scale_pos_weight
        train_params = self.params.copy()
        train_params['scale_pos_weight'] = scale_pos_weight

        # Add monotonic constraints
        if feature_names:
            constraints = self._get_monotone_constraints(feature_names)
            train_params['monotone_constraints'] = constraints

        # Create datasets
        train_data = lgb.Dataset(
            X_train,
            label=y_train,
            feature_name=feature_names,
            categorical_feature=categorical_features,
        )

        valid_sets = [train_data]
        valid_names = ['train']

        if X_val is not None and y_val is not None:
            val_data = lgb.Dataset(
                X_val,
                label=y_val,
                reference=train_data,
                feature_name=feature_names,
                categorical_feature=categorical_features,
            )
            valid_sets.append(val_data)
            valid_names.append('valid')

        # Train model
        logger.info("Training LightGBM model...")

        self.model = lgb.train(
            train_params,
            train_data,
            num_boost_round=self.n_estimators,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=[
                lgb.early_stopping(self.early_stopping_rounds, verbose=False),
                lgb.log_evaluation(50),
            ],
        )

        self.best_iteration = self.model.best_iteration

        logger.info(f"Training complete. Best iteration: {self.best_iteration}")

        # Compute metrics
        metrics = {}

        # Training metrics
        y_train_pred = self.predict_proba(X_train)
        metrics['train_auc'] = roc_auc_score(y_train, y_train_pred)
        metrics['train_accuracy'] = accuracy_score(y_train, y_train_pred > 0.5)

        # Validation metrics
        if X_val is not None and y_val is not None:
            y_val_pred = self.predict_proba(X_val)
            metrics['val_auc'] = roc_auc_score(y_val, y_val_pred)
            metrics['val_accuracy'] = accuracy_score(y_val, y_val_pred > 0.5)

            # Precision/recall at different thresholds
            for threshold in [0.5, 0.7, 0.9, 0.95]:
                y_val_pred_binary = (y_val_pred >= threshold).astype(int)
                if np.sum(y_val_pred_binary) > 0:  # Check for predictions
                    metrics[f'val_precision_at_{int(threshold*100)}'] = precision_score(
                        y_val, y_val_pred_binary, zero_division=0
                    )
                    metrics[f'val_recall_at_{int(threshold*100)}'] = recall_score(
                        y_val, y_val_pred_binary, zero_division=0
                    )

        logger.info("Training metrics:")
        for key, value in metrics.items():
            logger.info(f"  {key}: {value:.4f}")

        return metrics

    def cross_validate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None,
        n_splits: int = 5,
        random_state: int = 42,
    ) -> List[Dict[str, float]]:
        """
        Perform stratified cross-validation.

        Args:
            X: Features
            y: Labels
            feature_names: List of feature names
            n_splits: Number of CV folds
            random_state: Random seed

        Returns:
            List of metric dictionaries (one per fold)
        """
        logger.info(f"Performing {n_splits}-fold cross-validation...")

        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)

        cv_scores = []

        for fold, (train_idx, val_idx) in enumerate(skf.split(X, y)):
            logger.info(f"Fold {fold + 1}/{n_splits}")

            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # Train on this fold
            metrics = self.train(X_train, y_train, X_val, y_val, feature_names)
            metrics['fold'] = fold
            cv_scores.append(metrics)

        self.cv_scores = cv_scores

        # Compute mean metrics
        mean_metrics = {}
        for key in cv_scores[0].keys():
            if key != 'fold':
                values = [score[key] for score in cv_scores if key in score]
                mean_metrics[f'mean_{key}'] = np.mean(values)
                mean_metrics[f'std_{key}'] = np.std(values)

        logger.info("Cross-validation summary:")
        for key, value in mean_metrics.items():
            logger.info(f"  {key}: {value:.4f}")

        return cv_scores

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict match probabilities.

        Args:
            X: Features (n_samples, n_features)

        Returns:
            Array of probabilities (n_samples,)
        """
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        return self.model.predict(X, num_iteration=self.best_iteration)

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        """
        Predict binary match labels.

        Args:
            X: Features (n_samples, n_features)
            threshold: Classification threshold

        Returns:
            Array of binary predictions (n_samples,)
        """
        proba = self.predict_proba(X)
        return (proba >= threshold).astype(int)

    def get_feature_importance(
        self,
        importance_type: str = 'gain',
    ) -> Dict[str, float]:
        """
        Get feature importance.

        Args:
            importance_type: 'gain' (default) or 'split'

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if self.model is None:
            raise RuntimeError("Model not trained.")

        importance = self.model.feature_importance(importance_type=importance_type)

        if self.feature_names:
            return dict(zip(self.feature_names, importance))
        else:
            return {f'feature_{i}': imp for i, imp in enumerate(importance)}

    def save(self, output_dir: str, version: str = 'v1'):
        """
        Save model to disk.

        Args:
            output_dir: Directory to save model
            version: Model version identifier
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save LightGBM model
        model_file = output_path / f'matcher_{version}.txt'
        self.model.save_model(str(model_file))
        logger.info(f"Model saved to {model_file}")

        # Save metadata
        metadata = {
            'version': version,
            'params': self.params,
            'n_estimators': self.n_estimators,
            'best_iteration': self.best_iteration,
            'feature_names': self.feature_names,
            'cv_scores': self.cv_scores,
        }

        metadata_file = output_path / f'matcher_{version}_metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Metadata saved to {metadata_file}")

    @classmethod
    def load(cls, model_path: str, metadata_path: Optional[str] = None) -> 'EntityMatchingModel':
        """
        Load model from disk.

        Args:
            model_path: Path to LightGBM model file
            metadata_path: Path to metadata JSON (optional)

        Returns:
            EntityMatchingModel instance
        """
        # Load LightGBM model
        lgb_model = lgb.Booster(model_file=str(model_path))

        # Create instance
        instance = cls()
        instance.model = lgb_model

        # Load metadata if available
        if metadata_path and Path(metadata_path).exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                instance.params = metadata.get('params', DEFAULT_PARAMS)
                instance.n_estimators = metadata.get('n_estimators', 500)
                instance.best_iteration = metadata.get('best_iteration')
                instance.feature_names = metadata.get('feature_names')
                instance.cv_scores = metadata.get('cv_scores', [])

        logger.info(f"Model loaded from {model_path}")

        return instance

    def load_for_gpu_inference(self, model_path: Optional[str] = None) -> bool:
        """
        Load model for GPU inference using available backend.

        Tries backends in order:
        1. cuML FIL (Linux only, fastest - 50-150x speedup)
        2. ONNX Runtime with DirectML/CUDA (Windows/Linux, 10-50x speedup)

        Args:
            model_path: Path to saved LightGBM model file. If None, saves
                       current model to a temp file.

        Returns:
            True if GPU initialization successful, False otherwise
        """
        if self.model is None:
            raise RuntimeError("Model not trained/loaded. Call train() or load() first.")

        # Try cuML first (Linux only, fastest)
        if self._try_cuml_gpu(model_path):
            return True

        # Try ONNX Runtime (Windows/Linux)
        if self._try_onnx_gpu():
            return True

        logger.warning(
            "No GPU backend available. Install one of:\n"
            "  - Linux: pip install cuml-cu12 (or conda install -c rapidsai cuml)\n"
            "  - Windows: pip install onnxruntime-gpu onnxmltools"
        )
        return False

    def _try_cuml_gpu(self, model_path: Optional[str] = None) -> bool:
        """Try to initialize cuML FIL backend (Linux only)."""
        try:
            from cuml import ForestInference
        except ImportError:
            logger.debug("cuML not available (Linux only)")
            return False

        try:
            import tempfile
            import os

            # Save model to temp file if path not provided
            if model_path is None:
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w', suffix='.txt', delete=False
                )
                model_path = temp_file.name
                temp_file.close()
                self.model.save_model(model_path)
                cleanup_temp = True
            else:
                cleanup_temp = False

            # Load into FIL
            self.fil_model = ForestInference.load(
                model_path,
                model_type='lightgbm',
                output_class=True,
            )

            if cleanup_temp:
                os.unlink(model_path)

            self._gpu_available = True
            self._gpu_backend = 'cuml'
            logger.info("GPU inference initialized with cuML FIL")
            return True

        except Exception as e:
            logger.debug(f"cuML initialization failed: {e}")
            return False

    def _try_onnx_gpu(self) -> bool:
        """Try to initialize ONNX Runtime GPU backend (Windows/Linux)."""
        try:
            import onnxruntime as ort
            import onnxmltools
            from onnxmltools.convert import convert_lightgbm
            from onnxmltools.convert.common.data_types import FloatTensorType
        except ImportError:
            logger.debug("ONNX Runtime or onnxmltools not available")
            return False

        try:
            # Check for GPU execution provider
            available_providers = ort.get_available_providers()
            gpu_provider = None

            if 'CUDAExecutionProvider' in available_providers:
                gpu_provider = 'CUDAExecutionProvider'
            elif 'DmlExecutionProvider' in available_providers:
                gpu_provider = 'DmlExecutionProvider'  # DirectML for Windows

            if gpu_provider is None:
                logger.debug("No GPU execution provider available in ONNX Runtime")
                return False

            # Convert LightGBM model to ONNX
            n_features = self.model.num_feature()
            initial_type = [('input', FloatTensorType([None, n_features]))]

            onnx_model = convert_lightgbm(
                self.model,
                initial_types=initial_type,
                target_opset=15,
            )

            # Create ONNX Runtime session with GPU
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self.onnx_session = ort.InferenceSession(
                onnx_model.SerializeToString(),
                sess_options,
                providers=[gpu_provider, 'CPUExecutionProvider'],
            )

            self._gpu_available = True
            self._gpu_backend = 'onnx'
            logger.info(f"GPU inference initialized with ONNX Runtime ({gpu_provider})")
            return True

        except Exception as e:
            logger.debug(f"ONNX Runtime GPU initialization failed: {e}")
            return False

    def predict_proba_gpu(self, X: np.ndarray) -> np.ndarray:
        """
        Predict match probabilities using GPU.

        Uses whichever GPU backend was successfully initialized.
        Thread-safe: Uses a lock to serialize GPU access (cuML is not thread-safe).

        Args:
            X: Features (n_samples, n_features)

        Returns:
            Array of probabilities (n_samples,)
        """
        if not self.is_gpu_available():
            raise RuntimeError(
                "GPU model not initialized. Call load_for_gpu_inference() first."
            )

        backend = getattr(self, '_gpu_backend', None)

        # Serialize GPU access - cuML/cupy is not thread-safe
        with self._gpu_lock:
            try:
                if backend == 'cuml':
                    return self._predict_cuml(X)
                elif backend == 'onnx':
                    return self._predict_onnx(X)
                else:
                    raise RuntimeError(f"Unknown GPU backend: {backend}")

            except Exception as e:
                logger.warning(f"GPU prediction failed, falling back to CPU: {e}")
                return self.predict_proba(X)

    def _predict_cuml(self, X: np.ndarray) -> np.ndarray:
        """Predict using cuML FIL."""
        import cupy as cp

        X_gpu = cp.asarray(X, dtype=cp.float32)
        proba_gpu = self.fil_model.predict_proba(X_gpu)

        if proba_gpu.ndim == 2:
            return cp.asnumpy(proba_gpu[:, 1])
        return cp.asnumpy(proba_gpu)

    def _predict_onnx(self, X: np.ndarray) -> np.ndarray:
        """Predict using ONNX Runtime."""
        X_float = X.astype(np.float32)
        input_name = self.onnx_session.get_inputs()[0].name

        # Run inference
        outputs = self.onnx_session.run(None, {input_name: X_float})

        # Output format: [labels, probabilities]
        # probabilities shape: (n_samples, 2) for binary classification
        if len(outputs) > 1:
            proba = outputs[1]  # Probability output
            if isinstance(proba, list):
                # List of dicts [{0: prob0, 1: prob1}, ...]
                return np.array([p.get(1, p.get('1', 0.5)) for p in proba], dtype=np.float32)
            elif proba.ndim == 2:
                return proba[:, 1].astype(np.float32)
            return proba.astype(np.float32)
        else:
            # Only labels output, use as probabilities
            return outputs[0].astype(np.float32)

    def is_gpu_available(self) -> bool:
        """Check if GPU inference is available."""
        return getattr(self, '_gpu_available', False)

    def get_gpu_backend(self) -> Optional[str]:
        """Get the name of the active GPU backend."""
        if self.is_gpu_available():
            return getattr(self, '_gpu_backend', None)
        return None
