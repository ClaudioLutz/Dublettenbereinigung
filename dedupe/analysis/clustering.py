"""
K-modes clustering module for categorical/binary rule features.

This module implements k-modes clustering (NOT k-means) for pattern discovery
on binary rule features. K-modes uses Hamming distance for categorical data.
"""

from typing import Tuple, Dict
import numpy as np
import pandas as pd
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
