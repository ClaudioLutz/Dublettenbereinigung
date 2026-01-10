"""
K-modes clustering module for categorical/binary rule features.

This module implements k-modes clustering (NOT k-means) for pattern discovery
on binary rule features. K-modes uses Hamming distance for categorical data.

Story 2.1: Added model export functions for YAML persistence.
"""

from typing import Tuple, Dict, List, Optional
from pathlib import Path
from datetime import date
import re
import numpy as np
import pandas as pd
import yaml
from kmodes.kmodes import KModes
from sklearn.metrics import silhouette_score
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for Windows compatibility
import matplotlib.pyplot as plt
import seaborn as sns


def perform_kmodes_clustering(
    X: np.ndarray,
    n_clusters: int = 15,
    random_state: int = 42
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Perform k-modes clustering on binary feature matrix.

    Args:
        X: Binary feature matrix of shape (n_samples, n_features)
        n_clusters: Number of clusters (default: 15)
        random_state: Random seed for reproducibility (default: 42)

    Returns:
        Tuple of (cluster_labels, cluster_centroids, cost)
        - cluster_labels: Array of cluster assignments for each sample
        - cluster_centroids: Array of cluster centroids (modes)
        - cost: Final clustering cost (sum of Hamming distances to centroids)
    """
    print(f"Running k-modes clustering with k={n_clusters}...")

    # Initialize k-modes
    km = KModes(
        n_clusters=n_clusters,
        init='Huang',  # Huang initialization method for k-modes
        n_init=1,  # Single run for speed (use 3-5 for production, 10 for research)
        n_jobs=-1,  # Use all CPU cores
        random_state=random_state,
        verbose=1  # Enable progress output
    )

    # Fit the model
    cluster_labels = km.fit_predict(X)
    cluster_centroids = km.cluster_centroids_
    cost = km.cost_

    print(f"Clustering complete. Cost: {cost:.2f}")
    print(f"Cluster sizes: {np.bincount(cluster_labels)}")

    return cluster_labels, cluster_centroids, cost


def validate_k_silhouette(
    X: np.ndarray,
    k_range: range = range(5, 31)
) -> Dict[str, Dict[int, float]]:
    """
    Validate optimal k using Silhouette analysis across multiple k values.

    Args:
        X: Binary feature matrix of shape (n_samples, n_features)
        k_range: Range of k values to test (default: 5 to 30)

    Returns:
        Dictionary with 'silhouette' and 'cost' subdicts mapping k to metric values
    """
    print(f"Running Silhouette validation for k in range {k_range.start}-{k_range.stop-1}...")

    silhouette_scores = {}
    costs = {}

    for k in k_range:
        print(f"  Testing k={k}...", end=' ')

        # Run k-modes clustering
        labels, centroids, cost = perform_kmodes_clustering(X, n_clusters=k, random_state=42)

        # Calculate Silhouette score with Hamming distance
        try:
            score = silhouette_score(X, labels, metric='hamming')
            silhouette_scores[k] = score
            costs[k] = cost
            print(f"Silhouette={score:.4f}, Cost={cost:.2f}")
        except Exception as e:
            print(f"Error: {e}")
            silhouette_scores[k] = -1.0  # Invalid score
            costs[k] = cost

    return {'silhouette': silhouette_scores, 'cost': costs}


def plot_cluster_validation(
    silhouette_scores: Dict[int, float],
    costs: Dict[int, float],
    current_k: int = 15,
    output_path: str = None
) -> None:
    """
    Generate cluster validation plots (Silhouette + Elbow).

    Creates a 2-panel figure with Silhouette score and Elbow (cost) plots.
    Marks the current k value with a vertical line for reference.

    Args:
        silhouette_scores: Dictionary mapping k to Silhouette score
        costs: Dictionary mapping k to clustering cost
        current_k: Current k value to highlight (default: 15)
        output_path: Path to save plot (PNG + SVG formats)
    """
    print("Generating cluster validation plots...")

    # Set visualization standards
    plt.rcParams['figure.dpi'] = 300
    plt.rcParams['savefig.dpi'] = 300
    plt.rcParams['font.size'] = 10
    plt.rcParams['axes.labelsize'] = 12
    plt.rcParams['axes.titlesize'] = 14
    plt.rcParams['xtick.labelsize'] = 10
    plt.rcParams['ytick.labelsize'] = 10
    plt.rcParams['legend.fontsize'] = 10

    # Create figure with 2 panels
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

    # Sort k values for plotting
    k_values = sorted(silhouette_scores.keys())
    sil_values = [silhouette_scores[k] for k in k_values]
    cost_values = [costs[k] for k in k_values]

    # Panel 1: Silhouette Score
    ax1.plot(k_values, sil_values, marker='o', linewidth=2, markersize=6, color='#1f77b4')
    ax1.axvline(current_k, color='red', linestyle='--', linewidth=2, alpha=0.7, label=f'Current k={current_k}')
    ax1.axhline(0.3, color='orange', linestyle=':', linewidth=1, alpha=0.5, label='Min acceptable (0.3)')
    ax1.axhline(0.5, color='green', linestyle=':', linewidth=1, alpha=0.5, label='Target (0.5)')
    ax1.set_xlabel('Number of Clusters (k)')
    ax1.set_ylabel('Silhouette Score')
    ax1.set_title('Silhouette Analysis (Hamming Distance)')
    ax1.grid(True, alpha=0.3, color='gray', linestyle='-', linewidth=0.5)
    ax1.legend(loc='best')

    # Panel 2: Elbow Plot
    ax2.plot(k_values, cost_values, marker='s', linewidth=2, markersize=6, color='#ff7f0e')
    ax2.axvline(current_k, color='red', linestyle='--', linewidth=2, alpha=0.7, label=f'Current k={current_k}')
    ax2.set_xlabel('Number of Clusters (k)')
    ax2.set_ylabel('Clustering Cost')
    ax2.set_title('Elbow Method (K-modes Cost)')
    ax2.grid(True, alpha=0.3, color='gray', linestyle='-', linewidth=0.5)
    ax2.legend(loc='best')

    plt.tight_layout()

    # Save plots
    if output_path:
        # Save PNG (primary)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Saved PNG: {output_path}")

        # Save SVG (scalable)
        svg_path = output_path.replace('.png', '.svg')
        plt.savefig(svg_path, format='svg', bbox_inches='tight')
        print(f"Saved SVG: {svg_path}")

    plt.close()


def get_cluster_profiles(
    centroids: np.ndarray,
    feature_names: list
) -> pd.DataFrame:
    """
    Convert cluster centroids to readable profiles.

    Args:
        centroids: Array of cluster centroids (modes) from k-modes
        feature_names: List of feature names corresponding to columns

    Returns:
        DataFrame with cluster profiles (one row per cluster, columns are features)
    """
    print("Generating cluster profiles...")

    # Convert to DataFrame
    profiles_df = pd.DataFrame(
        centroids,
        columns=feature_names
    )

    # Add cluster ID column
    profiles_df.insert(0, 'cluster_id', range(len(profiles_df)))

    # Add summary column: count of active features (value=1)
    profiles_df['active_features_count'] = (centroids == 1).sum(axis=1)

    print(f"Generated profiles for {len(profiles_df)} clusters")
    return profiles_df


def interpret_cluster_profile(profile_row: pd.Series, feature_names: list) -> str:
    """
    Generate human-readable interpretation of a cluster profile.

    Args:
        profile_row: Row from cluster profiles DataFrame
        feature_names: List of all feature names

    Returns:
        String description of the cluster's characteristics
    """
    cluster_id = profile_row.get('cluster_id', 'Unknown')
    active_features = [fname for fname in feature_names if profile_row.get(fname, 0) == 1]

    if not active_features:
        return f"Cluster {cluster_id}: No dominant features (sparse pattern)"

    # Categorize active features
    match_types = [f for f in active_features if any(f.startswith(prefix) for prefix in
                   ['exact_', 'fuzzy_', 'address_assisted_', 'phonetic_assisted_'])]
    gates = [f for f in active_features if f.startswith('gate_')]
    quality = [f for f in active_features if any(f.startswith(prefix) for prefix in
               ['both_', 'one_', 'yob_only_'])]
    similarity = [f for f in active_features if any(f.startswith(prefix) for prefix in
                  ['name_similarity_', 'address_ratio_', 'first_', 'last_', 'different_'])]

    parts = [f"Cluster {cluster_id}:"]
    if match_types:
        parts.append(f"Match types: {', '.join(match_types[:3])}")
    if gates:
        parts.append(f"Gates: {', '.join(gates)}")
    if quality:
        parts.append(f"Data quality: {', '.join(quality[:2])}")
    if similarity:
        parts.append(f"Similarity: {', '.join(similarity[:2])}")

    return " | ".join(parts)


def evaluate_clustering_quality(silhouette_score_value: float) -> str:
    """
    Evaluate clustering quality based on Silhouette score.

    Args:
        silhouette_score_value: Silhouette score (0.0-1.0, higher is better)

    Returns:
        String assessment of clustering quality
    """
    if silhouette_score_value >= 0.7:
        return "EXCELLENT - Very strong, well-defined clusters"
    elif silhouette_score_value >= 0.5:
        return "GOOD - Well-defined clusters (target quality)"
    elif silhouette_score_value >= 0.3:
        return "ACCEPTABLE - Clusters are distinguishable but suboptimal"
    elif silhouette_score_value >= 0.0:
        return "POOR - Weak clustering structure, results may not be reliable"
    else:
        return "INVALID - Clustering failed or data not suitable"


# ============================================================================
# Story 2.1: Model Export Functions
# ============================================================================


def export_cluster_model(
    centroids: np.ndarray,
    feature_names: List[str],
    output_path: Path,
    model_version: str = "v1",
    silhouette_score: Optional[float] = None,
    validation_date: Optional[str] = None
) -> None:
    """
    Export k-modes cluster model to YAML format.

    Creates a human-readable YAML file containing cluster centroids and
    metadata. This file can be loaded by the cluster classifier without
    requiring the kmodes library.

    Args:
        centroids: Cluster centroids array of shape (n_clusters, n_features)
        feature_names: List of feature names corresponding to columns
        output_path: Path to save YAML file (e.g., models/cluster_model_v1.yaml)
        model_version: Semantic version string (e.g., "v1", "v2")
        silhouette_score: Optional clustering quality score (0.0-1.0)
        validation_date: Optional LLM validation date (ISO format)

    Returns:
        None

    Raises:
        ValueError: If centroid dimensions don't match feature count

    Example:
        >>> export_cluster_model(
        ...     centroids=km.cluster_centroids_,
        ...     feature_names=['f0', 'f1', 'f2'],
        ...     output_path=Path("models/cluster_model_v1.yaml"),
        ...     model_version="v1",
        ...     silhouette_score=0.42
        ... )
    """
    output_path = Path(output_path)
    n_clusters, n_features = centroids.shape

    # Validate dimensions
    if len(feature_names) != n_features:
        raise ValueError(
            f"Feature name count ({len(feature_names)}) doesn't match "
            f"centroid dimensions ({n_features})"
        )

    # Build model configuration
    model_config = {
        'version': '1.0',
        'model_version': model_version,
        'created_date': date.today().isoformat(),
        'n_clusters': int(n_clusters),
        'n_features': int(n_features),
        'feature_names': list(feature_names),
        'centroids': {}
    }

    # Add optional metadata
    if silhouette_score is not None:
        model_config['silhouette_score'] = float(silhouette_score)

    if validation_date is not None:
        model_config['validation_date'] = validation_date

    # Convert centroids to dictionary format
    for cluster_id in range(n_clusters):
        # Ensure values are Python int (not numpy int64)
        centroid_values = [int(v) for v in centroids[cluster_id]]
        model_config['centroids'][cluster_id] = centroid_values

    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write YAML file with clean formatting
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(
            model_config,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False
        )

    print(f"Exported cluster model to: {output_path}")
    print(f"  Version: {model_version}")
    print(f"  Clusters: {n_clusters}")
    print(f"  Features: {n_features}")


def validate_model_schema(model_path: Path) -> bool:
    """
    Validate YAML model file schema.

    Checks that the model file contains all required keys and that
    dimensions are consistent.

    Args:
        model_path: Path to YAML model file

    Returns:
        True if schema is valid

    Raises:
        FileNotFoundError: If model file doesn't exist
        ValueError: If schema is invalid with descriptive message
    """
    model_path = Path(model_path)

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    with open(model_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if config is None:
        raise ValueError(f"Empty or invalid YAML file: {model_path}")

    # Check required keys
    required_keys = ['version', 'n_clusters', 'n_features', 'centroids', 'feature_names']
    for key in required_keys:
        if key not in config:
            raise ValueError(
                f"Invalid model schema: missing '{key}' in {model_path}. "
                f"Required keys: {required_keys}"
            )

    # Validate dimensions
    n_features = config['n_features']
    n_clusters = config['n_clusters']

    # Check feature names count
    if len(config['feature_names']) != n_features:
        raise ValueError(
            f"Feature name count ({len(config['feature_names'])}) doesn't match "
            f"n_features ({n_features})"
        )

    # Check centroid dimensions
    for cluster_id, centroid in config['centroids'].items():
        if len(centroid) != n_features:
            raise ValueError(
                f"Centroid dimension mismatch: cluster {cluster_id} has "
                f"{len(centroid)} values, expected {n_features}"
            )

    print(f"Schema validation passed: {model_path}")
    return True


def get_next_model_version(models_dir: Path) -> str:
    """
    Determine next model version based on existing files.

    Scans the models directory for cluster_model_v*.yaml files and
    returns the next version number.

    Args:
        models_dir: Directory containing model files

    Returns:
        Version string (e.g., "v1", "v2", "v3")

    Example:
        >>> get_next_model_version(Path("models/"))
        "v1"  # No existing models
        >>> get_next_model_version(Path("models/"))
        "v3"  # After v1 and v2 exist
    """
    models_dir = Path(models_dir)

    if not models_dir.exists():
        return "v1"

    # Find existing model files
    pattern = re.compile(r'cluster_model_v(\d+)\.yaml')
    versions = []

    for file_path in models_dir.glob("cluster_model_v*.yaml"):
        match = pattern.match(file_path.name)
        if match:
            versions.append(int(match.group(1)))

    if not versions:
        return "v1"

    next_version = max(versions) + 1
    return f"v{next_version}"
