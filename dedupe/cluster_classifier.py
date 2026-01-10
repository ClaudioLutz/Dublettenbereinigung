"""
Cluster classifier using Hamming distance (Story 1.3, Story 2.2).

This module provides a classifier that assigns matched pairs to clusters
based on their rule activation patterns, using Hamming distance to find
the nearest cluster centroid.

Features:
- Single pair classification via classify_pair()
- Batch classification via classify_batch()
- Load centroids from YAML model file
- Graceful degradation with Tier 2 fallback (Story 2.2)
- Deterministic tie-breaking (lowest cluster ID wins)
- Optimized for performance with NumPy vectorization

Usage:
    from dedupe.cluster_classifier import HammingDistanceClassifier, load_centroids_from_yaml

    # Load centroids from model file
    centroids = load_centroids_from_yaml(Path("models/cluster_model_v1.yaml"))

    # Create classifier
    classifier = HammingDistanceClassifier(centroids)

    # Classify single pair
    cluster_id = classifier.classify_pair(feature_vector)

    # Classify batch
    df_with_clusters = classifier.classify_batch(df, feature_columns)

Story 2.2: Added graceful degradation with load_cluster_model_with_fallback()
"""

from pathlib import Path
from typing import Dict, List, Union, Optional, Any
from collections import Counter
import logging
import numpy as np
import pandas as pd
import yaml

# Configure module logger
logger = logging.getLogger(__name__)


def hamming_distance(vec1: np.ndarray, vec2: np.ndarray) -> int:
    """
    Calculate Hamming distance between two binary vectors.

    Hamming distance is the number of positions where the two vectors differ.

    Args:
        vec1: First binary vector (numpy array of 0s and 1s)
        vec2: Second binary vector (numpy array of 0s and 1s)

    Returns:
        Integer count of differing positions

    Example:
        >>> hamming_distance(np.array([1, 0, 1]), np.array([1, 1, 1]))
        1  # Position 1 differs
    """
    return int(np.sum(vec1 != vec2))


class HammingDistanceClassifier:
    """
    Classify pairs into clusters using Hamming distance.

    This classifier assigns pairs to the cluster whose centroid has the
    minimum Hamming distance from the pair's feature vector. Ties are
    broken by choosing the lowest cluster ID (deterministic behavior).

    Attributes:
        centroids: Dictionary mapping cluster_id -> centroid vector
        n_clusters: Number of clusters
        n_features: Number of features per vector

    Example:
        >>> centroids = {0: np.array([1, 1, 1]), 1: np.array([0, 0, 0])}
        >>> classifier = HammingDistanceClassifier(centroids)
        >>> classifier.classify_pair(np.array([1, 1, 0]))
        0  # Closest to cluster 0
    """

    def __init__(self, centroids: Dict[int, np.ndarray]):
        """
        Initialize classifier with cluster centroids.

        Args:
            centroids: Dictionary mapping cluster_id (int) -> centroid vector (numpy array)

        Raises:
            ValueError: If centroids is empty or vectors have inconsistent lengths
        """
        if not centroids:
            raise ValueError("Centroids dictionary cannot be empty")

        self.centroids = {k: np.asarray(v) for k, v in centroids.items()}
        self.n_clusters = len(centroids)
        self.n_features = len(next(iter(self.centroids.values())))

        # Pre-compute centroid matrix for batch operations
        self._cluster_ids = sorted(self.centroids.keys())
        self._centroid_matrix = np.array([self.centroids[k] for k in self._cluster_ids])

    def classify_pair(self, features: Union[np.ndarray, List[int]]) -> int:
        """
        Classify a single pair to nearest cluster.

        Args:
            features: Binary feature vector (list or numpy array)

        Returns:
            Cluster ID (integer) of nearest cluster

        Example:
            >>> classifier.classify_pair([1, 0, 1, 0, 1])
            3  # Nearest cluster
        """
        features = np.asarray(features)

        # Calculate distance to each centroid
        distances = []
        for cluster_id in self._cluster_ids:
            dist = hamming_distance(features, self.centroids[cluster_id])
            distances.append((cluster_id, dist))

        # Find minimum distance (tie-break: lowest cluster ID due to sorted order)
        min_cluster_id = min(distances, key=lambda x: (x[1], x[0]))[0]

        return min_cluster_id

    def classify_batch(
        self,
        df: pd.DataFrame,
        feature_cols: List[str]
    ) -> pd.DataFrame:
        """
        Classify all pairs in DataFrame.

        Uses vectorized NumPy operations for performance.

        Args:
            df: DataFrame with feature columns
            feature_cols: List of column names containing binary features

        Returns:
            DataFrame with added 'cluster' column

        Example:
            >>> df_classified = classifier.classify_batch(df, ['f0', 'f1', 'f2'])
            >>> df_classified['cluster']
            0    3
            1    7
            2    0
            dtype: int64
        """
        result_df = df.copy()

        # Extract feature matrix
        X = df[feature_cols].values

        # Vectorized Hamming distance calculation
        # For each row in X, calculate distance to each centroid
        # X shape: (n_samples, n_features)
        # centroids shape: (n_clusters, n_features)

        # Broadcast comparison: (n_samples, 1, n_features) != (1, n_clusters, n_features)
        # Result: (n_samples, n_clusters, n_features) -> sum -> (n_samples, n_clusters)
        distances = np.sum(X[:, np.newaxis, :] != self._centroid_matrix[np.newaxis, :, :], axis=2)

        # Find cluster with minimum distance (argmin returns first occurrence for ties)
        min_indices = np.argmin(distances, axis=1)

        # Map indices back to cluster IDs
        cluster_assignments = np.array([self._cluster_ids[i] for i in min_indices])

        result_df['cluster'] = cluster_assignments

        return result_df


def load_centroids_from_yaml(model_path: Path) -> Dict[int, np.ndarray]:
    """
    Load cluster centroids from YAML model file.

    Args:
        model_path: Path to YAML file containing cluster centroids

    Returns:
        Dictionary mapping cluster_id -> centroid vector (numpy array)

    Raises:
        FileNotFoundError: If model file doesn't exist
        ValueError: If YAML schema is invalid

    Expected YAML schema:
        version: "1.0"
        n_clusters: 15
        n_features: 35
        centroids:
          0: [1, 0, 1, ...]
          1: [0, 1, 0, ...]
          ...
    """
    if not model_path.exists():
        raise FileNotFoundError(f"Cluster model file not found: {model_path}")

    with open(model_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if config is None or 'centroids' not in config:
        raise ValueError(
            f"Invalid model schema: missing 'centroids' key in {model_path}. "
            f"Expected format:\n"
            f"  centroids:\n"
            f"    0: [1, 0, 1, ...]\n"
            f"    1: [0, 1, 0, ...]\n"
            f"    ..."
        )

    centroids = {}
    for cluster_id, centroid_values in config['centroids'].items():
        # Convert string keys to int if needed
        cluster_id = int(cluster_id)
        centroids[cluster_id] = np.array(centroid_values, dtype=int)

    return centroids


def get_cluster_distribution(cluster_assignments: List[int]) -> Dict[int, int]:
    """
    Calculate distribution of pairs across clusters.

    Args:
        cluster_assignments: List of cluster IDs

    Returns:
        Dictionary mapping cluster_id -> count of pairs

    Example:
        >>> get_cluster_distribution([0, 0, 1, 2, 2, 2])
        {0: 2, 1: 1, 2: 3}
    """
    return dict(Counter(cluster_assignments))


def log_cluster_statistics(
    cluster_assignments: List[int],
    classification_time: float
) -> None:
    """
    Log cluster distribution and classification statistics.

    Args:
        cluster_assignments: List of cluster IDs
        classification_time: Time taken for classification in seconds
    """
    distribution = get_cluster_distribution(cluster_assignments)
    total = len(cluster_assignments)

    print("\nCluster Distribution Statistics:")
    print("-" * 40)
    for cluster_id in sorted(distribution.keys()):
        count = distribution[cluster_id]
        pct = (count / total) * 100
        print(f"  Cluster {cluster_id:2d}: {count:6,} pairs ({pct:5.1f}%)")

    print("-" * 40)
    print(f"  Total:       {total:6,} pairs")
    print(f"  Classification time: {classification_time:.2f} seconds")


# ============================================================================
# Story 2.2: Model Loading with Graceful Degradation
# ============================================================================


def load_cluster_model(model_path: Path) -> Dict[str, Any]:
    """
    Load complete cluster model from YAML file.

    Returns the full model configuration including centroids and metadata.

    Args:
        model_path: Path to YAML model file

    Returns:
        Dictionary with model data:
        - centroids: Dict[int, np.ndarray]
        - model_version: str
        - n_clusters: int
        - n_features: int
        - feature_names: List[str]
        - silhouette_score: float (optional)

    Raises:
        FileNotFoundError: If model file doesn't exist
        ValueError: If YAML schema is invalid

    Example:
        >>> model = load_cluster_model(Path("models/cluster_model_v1.yaml"))
        >>> model['model_version']
        'v1'
        >>> model['centroids'][0]
        array([1, 0, 1, ...])
    """
    model_path = Path(model_path)

    if not model_path.exists():
        raise FileNotFoundError(f"Cluster model file not found: {model_path}")

    with open(model_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if config is None:
        raise ValueError(f"Empty or invalid YAML file: {model_path}")

    if 'centroids' not in config:
        raise ValueError(
            f"Invalid model schema: missing 'centroids' key in {model_path}. "
            f"Re-export model using export_cluster_model() or restore from git."
        )

    # Convert centroids to numpy arrays
    centroids = {}
    for cluster_id, centroid_values in config['centroids'].items():
        cluster_id = int(cluster_id)
        centroids[cluster_id] = np.array(centroid_values, dtype=int)

    config['centroids'] = centroids

    logger.info(
        f"Model loaded successfully (version: {config.get('model_version', 'unknown')}, "
        f"clusters: {config.get('n_clusters', len(centroids))}, "
        f"features: {config.get('n_features', 'unknown')})"
    )

    return config


def load_cluster_model_with_fallback(
    model_path: Path
) -> Optional[Dict[str, Any]]:
    """
    Load model with graceful degradation on failure.

    If the model file is missing or corrupt, logs an appropriate message
    and returns None. The caller should handle the fallback behavior
    (e.g., assign all pairs to Tier 2).

    Args:
        model_path: Path to YAML model file

    Returns:
        Model data dictionary if successful, None if failed

    Example:
        >>> model = load_cluster_model_with_fallback(Path("models/cluster_model_v1.yaml"))
        >>> if model is None:
        ...     classifier = create_tier2_fallback_classifier()
        ... else:
        ...     classifier = HammingDistanceClassifier(model['centroids'])
    """
    model_path = Path(model_path)

    try:
        return load_cluster_model(model_path)

    except FileNotFoundError:
        logger.warning(
            f"Cluster model not found: {model_path} - defaulting to Tier 2. "
            f"Run export_cluster_model() to create model file."
        )
        return None

    except yaml.YAMLError as e:
        logger.error(
            f"Corrupt cluster model: {model_path} - YAML parsing failed. "
            f"Error: {e}. "
            f"Remediation: Re-export model using export_cluster_model() or restore from git."
        )
        return None

    except ValueError as e:
        logger.error(
            f"Invalid cluster model schema: {model_path}. "
            f"Error: {e}. "
            f"Remediation: Re-export model using export_cluster_model() or restore from git."
        )
        return None

    except Exception as e:
        logger.error(
            f"Unexpected error loading cluster model: {model_path}. "
            f"Error: {type(e).__name__}: {e}. "
            f"Defaulting to Tier 2."
        )
        return None


def create_tier2_fallback_classifier(n_features: int = 35) -> HammingDistanceClassifier:
    """
    Create a fallback classifier that assigns all pairs to cluster 0 (Tier 2).

    Used when model loading fails to ensure safe fallback behavior.
    Cluster 0 is mapped to Tier 2 in the default cluster tier mapping,
    ensuring all pairs go to manual review.

    Args:
        n_features: Number of features in feature vectors (default: 35)

    Returns:
        HammingDistanceClassifier that assigns all pairs to cluster 0

    Example:
        >>> classifier = create_tier2_fallback_classifier()
        >>> classifier.classify_pair([1, 0, 1, 0, ...])
        0  # Always returns cluster 0 (Tier 2)
    """
    # Create a single centroid that matches any input
    # Using all zeros means any feature vector will have minimal distance
    fallback_centroid = np.zeros(n_features, dtype=int)

    centroids = {0: fallback_centroid}

    logger.warning(
        f"Created Tier 2 fallback classifier - all pairs will be assigned to cluster 0 (manual review)"
    )

    return HammingDistanceClassifier(centroids)
