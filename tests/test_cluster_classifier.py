"""
Unit tests for cluster classifier module (Story 1.3).

Tests the Hamming distance-based classifier that assigns pairs
to clusters based on their rule activation patterns.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestHammingDistance:
    """Test Hamming distance calculation."""

    def test_hamming_distance_identical_vectors(self):
        """Identical vectors should have distance 0."""
        from dedupe.cluster_classifier import hamming_distance

        vec1 = np.array([1, 0, 1, 0, 1])
        vec2 = np.array([1, 0, 1, 0, 1])

        assert hamming_distance(vec1, vec2) == 0

    def test_hamming_distance_all_different(self):
        """Completely different vectors should have max distance."""
        from dedupe.cluster_classifier import hamming_distance

        vec1 = np.array([1, 1, 1, 1, 1])
        vec2 = np.array([0, 0, 0, 0, 0])

        assert hamming_distance(vec1, vec2) == 5

    def test_hamming_distance_partial_difference(self):
        """Partially different vectors should have correct count."""
        from dedupe.cluster_classifier import hamming_distance

        vec1 = np.array([1, 0, 1, 0, 1])
        vec2 = np.array([1, 1, 1, 0, 0])  # Differs at positions 1 and 4

        assert hamming_distance(vec1, vec2) == 2

    def test_hamming_distance_single_difference(self):
        """Single bit difference should return 1."""
        from dedupe.cluster_classifier import hamming_distance

        vec1 = np.array([1, 0, 1, 0, 1])
        vec2 = np.array([1, 0, 0, 0, 1])  # Differs at position 2

        assert hamming_distance(vec1, vec2) == 1


class TestHammingDistanceClassifier:
    """Test HammingDistanceClassifier class."""

    @pytest.fixture
    def simple_centroids(self):
        """Create simple test centroids for 3 clusters with 5 features."""
        return {
            0: np.array([1, 1, 1, 1, 1]),  # All ones
            1: np.array([0, 0, 0, 0, 0]),  # All zeros
            2: np.array([1, 0, 1, 0, 1]),  # Alternating
        }

    @pytest.fixture
    def classifier(self, simple_centroids):
        """Create classifier with simple centroids."""
        from dedupe.cluster_classifier import HammingDistanceClassifier
        return HammingDistanceClassifier(simple_centroids)

    def test_classify_pair_nearest_cluster(self, classifier):
        """Should assign to cluster with minimum Hamming distance."""
        # Feature vector close to cluster 0 (all ones)
        features = np.array([1, 1, 1, 1, 0])  # Distance 1 from cluster 0

        result = classifier.classify_pair(features)

        assert result == 0, "Should classify to cluster 0 (nearest)"

    def test_classify_pair_exact_match(self, classifier):
        """Exact match to centroid should return that cluster."""
        features = np.array([0, 0, 0, 0, 0])  # Exact match to cluster 1

        result = classifier.classify_pair(features)

        assert result == 1, "Should classify to cluster 1 (exact match)"

    def test_classify_pair_tie_breaking_lowest_id(self, simple_centroids):
        """When tied, should return lowest cluster ID."""
        from dedupe.cluster_classifier import HammingDistanceClassifier

        # Create centroids where clusters 0 and 1 are equidistant from test vector
        # Test vector: [0, 1, 0, 1, 0]
        # Cluster 0: [1, 1, 0, 1, 0] - differs at position 0 only -> distance 1
        # Cluster 1: [0, 0, 0, 1, 0] - differs at position 1 only -> distance 1
        tied_centroids = {
            0: np.array([1, 1, 0, 1, 0]),  # Distance 1 from [0, 1, 0, 1, 0]
            1: np.array([0, 0, 0, 1, 0]),  # Distance 1 from [0, 1, 0, 1, 0]
        }
        classifier = HammingDistanceClassifier(tied_centroids)

        features = np.array([0, 1, 0, 1, 0])  # Equidistant from both (distance 1)

        result = classifier.classify_pair(features)

        assert result == 0, "Should return lowest cluster ID (0) when tied"

    def test_classify_batch_adds_cluster_column(self, classifier):
        """Batch classification should add 'cluster' column."""
        df = pd.DataFrame({
            'f0': [1, 0, 1],
            'f1': [1, 0, 0],
            'f2': [1, 0, 1],
            'f3': [1, 0, 0],
            'f4': [1, 0, 1],
        })
        feature_cols = ['f0', 'f1', 'f2', 'f3', 'f4']

        result = classifier.classify_batch(df, feature_cols)

        assert 'cluster' in result.columns, "Should add 'cluster' column"
        assert len(result) == 3, "Should preserve row count"

    def test_classify_batch_correct_assignments(self, classifier):
        """Batch classification should assign correct clusters."""
        df = pd.DataFrame({
            'f0': [1, 0],  # First row close to cluster 0, second to cluster 1
            'f1': [1, 0],
            'f2': [1, 0],
            'f3': [1, 0],
            'f4': [1, 0],
        })
        feature_cols = ['f0', 'f1', 'f2', 'f3', 'f4']

        result = classifier.classify_batch(df, feature_cols)

        assert result.iloc[0]['cluster'] == 0, "First row should be cluster 0"
        assert result.iloc[1]['cluster'] == 1, "Second row should be cluster 1"

    def test_classify_batch_preserves_original_columns(self, classifier):
        """Batch classification should preserve all original columns."""
        df = pd.DataFrame({
            'id': [1, 2],
            'name': ['Alice', 'Bob'],
            'f0': [1, 0],
            'f1': [1, 0],
            'f2': [1, 0],
            'f3': [1, 0],
            'f4': [1, 0],
        })
        feature_cols = ['f0', 'f1', 'f2', 'f3', 'f4']

        result = classifier.classify_batch(df, feature_cols)

        assert 'id' in result.columns, "Should preserve 'id' column"
        assert 'name' in result.columns, "Should preserve 'name' column"
        assert list(result['id']) == [1, 2], "Should preserve 'id' values"

    def test_classify_batch_deterministic(self, classifier):
        """Same input should produce same output (deterministic)."""
        df = pd.DataFrame({
            'f0': [1, 0, 1],
            'f1': [1, 0, 0],
            'f2': [1, 0, 1],
            'f3': [1, 0, 0],
            'f4': [1, 0, 1],
        })
        feature_cols = ['f0', 'f1', 'f2', 'f3', 'f4']

        result1 = classifier.classify_batch(df, feature_cols)
        result2 = classifier.classify_batch(df, feature_cols)

        assert list(result1['cluster']) == list(result2['cluster']), \
            "Should produce identical results on repeated calls"


class TestClassifierWithRealFeatures:
    """Test classifier with realistic 35-feature vectors."""

    @pytest.fixture
    def realistic_centroids(self):
        """Create realistic centroids mimicking actual cluster profiles."""
        np.random.seed(42)  # For reproducibility
        centroids = {}
        for i in range(15):  # 15 clusters
            # Create 35-feature centroids with varying patterns
            centroid = np.zeros(35, dtype=int)
            # Set some features based on cluster characteristics
            if i < 4:  # Tier 2 clusters (0, 1, 2, 5) - more varied
                centroid[:10] = np.random.randint(0, 2, 10)
            else:  # Tier 1 clusters - more consistent patterns
                centroid[i % 35] = 1  # Distinctive feature
                centroid[(i + 5) % 35] = 1
            centroids[i] = centroid
        return centroids

    @pytest.fixture
    def classifier(self, realistic_centroids):
        """Create classifier with realistic centroids."""
        from dedupe.cluster_classifier import HammingDistanceClassifier
        return HammingDistanceClassifier(realistic_centroids)

    def test_classify_35_features(self, classifier):
        """Should handle 35-feature vectors."""
        features = np.zeros(35, dtype=int)
        features[5] = 1
        features[10] = 1

        result = classifier.classify_pair(features)

        assert 0 <= result <= 14, "Should return valid cluster ID (0-14)"

    def test_batch_performance(self, classifier):
        """Should classify 1000 pairs quickly (proxy for 78k performance)."""
        np.random.seed(42)
        n_pairs = 1000
        df = pd.DataFrame(
            np.random.randint(0, 2, (n_pairs, 35)),
            columns=[f'f{i}' for i in range(35)]
        )
        feature_cols = [f'f{i}' for i in range(35)]

        start = time.time()
        result = classifier.classify_batch(df, feature_cols)
        elapsed = time.time() - start

        assert len(result) == n_pairs, "Should classify all pairs"
        assert elapsed < 1.0, f"Should classify 1000 pairs in <1s, took {elapsed:.2f}s"
        # Extrapolate: 78k pairs should take ~78x longer, so <78s (well under 10 min)


class TestLoadCentroids:
    """Test loading centroids from YAML file."""

    def test_load_centroids_missing_file(self, tmp_path):
        """Should raise error for missing file."""
        from dedupe.cluster_classifier import load_centroids_from_yaml

        with pytest.raises(FileNotFoundError):
            load_centroids_from_yaml(tmp_path / "nonexistent.yaml")

    def test_load_centroids_valid_yaml(self, tmp_path):
        """Should load valid YAML centroids."""
        from dedupe.cluster_classifier import load_centroids_from_yaml

        yaml_content = """
version: "1.0"
n_clusters: 3
n_features: 5
centroids:
  0: [1, 1, 1, 1, 1]
  1: [0, 0, 0, 0, 0]
  2: [1, 0, 1, 0, 1]
"""
        config_path = tmp_path / "model.yaml"
        config_path.write_text(yaml_content, encoding='utf-8')

        result = load_centroids_from_yaml(config_path)

        assert len(result) == 3, "Should load 3 centroids"
        assert list(result[0]) == [1, 1, 1, 1, 1], "Centroid 0 should match"
        assert list(result[1]) == [0, 0, 0, 0, 0], "Centroid 1 should match"

    def test_load_centroids_invalid_schema(self, tmp_path):
        """Should raise error for invalid schema."""
        from dedupe.cluster_classifier import load_centroids_from_yaml

        yaml_content = """
version: "1.0"
wrong_key:
  0: [1, 1, 1]
"""
        config_path = tmp_path / "invalid.yaml"
        config_path.write_text(yaml_content, encoding='utf-8')

        with pytest.raises(ValueError, match="missing 'centroids'"):
            load_centroids_from_yaml(config_path)


class TestClusterDistribution:
    """Test cluster distribution logging."""

    def test_get_cluster_distribution(self):
        """Should return correct cluster counts."""
        from dedupe.cluster_classifier import get_cluster_distribution

        clusters = [0, 0, 0, 1, 1, 2]

        result = get_cluster_distribution(clusters)

        assert result[0] == 3, "Cluster 0 should have 3 pairs"
        assert result[1] == 2, "Cluster 1 should have 2 pairs"
        assert result[2] == 1, "Cluster 2 should have 1 pair"
