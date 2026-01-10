"""
Unit tests for cluster classifier module (Story 1.3, Story 2.2).

Tests the Hamming distance-based classifier that assigns pairs
to clusters based on their rule activation patterns.

Story 2.2: Added tests for model loading with graceful degradation.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys
import time
import logging

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


# ============================================================================
# Story 2.2: Load K-Modes Model from YAML with Graceful Degradation
# ============================================================================


class TestLoadClusterModel:
    """Test model loading with graceful degradation (Story 2.2)."""

    @pytest.fixture
    def valid_model_yaml(self, tmp_path):
        """Create valid model YAML file for testing."""
        yaml_content = """
version: "1.0"
model_version: "v1"
created_date: "2026-01-10"
silhouette_score: 0.42
n_clusters: 3
n_features: 5
feature_names:
  - f0
  - f1
  - f2
  - f3
  - f4
centroids:
  0: [1, 1, 1, 1, 1]
  1: [0, 0, 0, 0, 0]
  2: [1, 0, 1, 0, 1]
"""
        config_path = tmp_path / "cluster_model_v1.yaml"
        config_path.write_text(yaml_content, encoding='utf-8')
        return config_path

    def test_load_cluster_model_success(self, valid_model_yaml):
        """Should load valid model successfully."""
        from dedupe.cluster_classifier import load_cluster_model

        result = load_cluster_model(valid_model_yaml)

        assert result is not None, "Should return model data"
        assert 'centroids' in result, "Should have centroids key"
        assert len(result['centroids']) == 3, "Should have 3 clusters"
        assert result['model_version'] == "v1", "Should have correct version"

    def test_load_cluster_model_returns_metadata(self, valid_model_yaml):
        """Should return model metadata."""
        from dedupe.cluster_classifier import load_cluster_model

        result = load_cluster_model(valid_model_yaml)

        assert result['n_clusters'] == 3, "Should have cluster count"
        assert result['n_features'] == 5, "Should have feature count"
        assert result['silhouette_score'] == 0.42, "Should have silhouette score"


class TestLoadClusterModelWithFallback:
    """Test graceful degradation on model load failure (Story 2.2)."""

    @pytest.fixture
    def valid_model_yaml(self, tmp_path):
        """Create valid model YAML file for testing."""
        yaml_content = """
version: "1.0"
model_version: "v1"
n_clusters: 3
n_features: 5
feature_names: [f0, f1, f2, f3, f4]
centroids:
  0: [1, 1, 1, 1, 1]
  1: [0, 0, 0, 0, 0]
  2: [1, 0, 1, 0, 1]
"""
        config_path = tmp_path / "cluster_model_v1.yaml"
        config_path.write_text(yaml_content, encoding='utf-8')
        return config_path

    def test_load_with_fallback_success(self, valid_model_yaml):
        """Should load valid model successfully."""
        from dedupe.cluster_classifier import load_cluster_model_with_fallback

        result = load_cluster_model_with_fallback(valid_model_yaml)

        assert result is not None, "Should return model data"
        assert 'centroids' in result, "Should have centroids"

    def test_load_with_fallback_missing_file(self, tmp_path, caplog):
        """Missing file should return None and log warning."""
        from dedupe.cluster_classifier import load_cluster_model_with_fallback

        missing_path = tmp_path / "nonexistent.yaml"

        with caplog.at_level(logging.WARNING):
            result = load_cluster_model_with_fallback(missing_path)

        assert result is None, "Should return None for missing file"
        assert "not found" in caplog.text.lower() or len(caplog.records) > 0, \
            "Should log warning about missing file"

    def test_load_with_fallback_corrupt_file(self, tmp_path, caplog):
        """Corrupt file should return None and log error."""
        from dedupe.cluster_classifier import load_cluster_model_with_fallback

        corrupt_content = "version: 1.0\n{{{invalid yaml"
        corrupt_path = tmp_path / "corrupt.yaml"
        corrupt_path.write_text(corrupt_content, encoding='utf-8')

        with caplog.at_level(logging.ERROR):
            result = load_cluster_model_with_fallback(corrupt_path)

        assert result is None, "Should return None for corrupt file"

    def test_load_with_fallback_missing_centroids(self, tmp_path, caplog):
        """Missing centroids key should return None and log error."""
        from dedupe.cluster_classifier import load_cluster_model_with_fallback

        yaml_content = """
version: "1.0"
model_version: "v1"
n_clusters: 3
n_features: 5
"""
        invalid_path = tmp_path / "invalid.yaml"
        invalid_path.write_text(yaml_content, encoding='utf-8')

        with caplog.at_level(logging.ERROR):
            result = load_cluster_model_with_fallback(invalid_path)

        assert result is None, "Should return None for missing centroids"


class TestTier2FallbackClassifier:
    """Test Tier 2 fallback behavior when model loading fails (Story 2.2)."""

    def test_create_tier2_fallback_classifier(self):
        """Should create classifier that assigns all pairs to Tier 2."""
        from dedupe.cluster_classifier import create_tier2_fallback_classifier

        classifier = create_tier2_fallback_classifier()

        assert classifier is not None, "Should create fallback classifier"

    def test_tier2_fallback_assigns_default_cluster(self):
        """Fallback classifier should assign default cluster (triggers Tier 2)."""
        from dedupe.cluster_classifier import create_tier2_fallback_classifier

        classifier = create_tier2_fallback_classifier(n_features=5)

        # Any feature vector should get cluster 0 (which maps to Tier 2)
        features = np.array([1, 0, 1, 0, 1])
        result = classifier.classify_pair(features)

        assert result == 0, "Fallback should assign cluster 0 (Tier 2)"

    def test_tier2_fallback_batch_classification(self):
        """Fallback classifier should work with batch classification."""
        from dedupe.cluster_classifier import create_tier2_fallback_classifier

        classifier = create_tier2_fallback_classifier(n_features=5)

        df = pd.DataFrame({
            'f0': [1, 0, 1],
            'f1': [1, 0, 0],
            'f2': [1, 0, 1],
            'f3': [1, 0, 0],
            'f4': [1, 0, 1],
        })
        feature_cols = ['f0', 'f1', 'f2', 'f3', 'f4']

        result = classifier.classify_batch(df, feature_cols)

        assert 'cluster' in result.columns, "Should add cluster column"
        assert all(result['cluster'] == 0), "All pairs should get cluster 0 (Tier 2)"


class TestLoadModelPerformance:
    """Test model loading performance (Story 2.2)."""

    def test_load_model_under_30_seconds(self, tmp_path):
        """Model loading should complete in ≤30 seconds."""
        from dedupe.cluster_classifier import load_cluster_model

        # Create a realistic model with 15 clusters and 35 features
        yaml_content = """
version: "1.0"
model_version: "v1"
n_clusters: 15
n_features: 35
feature_names:
"""
        # Add 35 feature names
        for i in range(35):
            yaml_content += f"  - feature_{i}\n"

        yaml_content += "centroids:\n"
        # Add 15 centroids with 35 values each
        np.random.seed(42)
        for cluster_id in range(15):
            values = [int(v) for v in np.random.randint(0, 2, 35)]
            yaml_content += f"  {cluster_id}: {values}\n"

        model_path = tmp_path / "large_model.yaml"
        model_path.write_text(yaml_content, encoding='utf-8')

        start = time.time()
        result = load_cluster_model(model_path)
        elapsed = time.time() - start

        assert result is not None, "Should load model"
        assert elapsed < 30.0, f"Load time should be <30s, was {elapsed:.2f}s"


# ============================================================================
# Story 2.3: Verify No ML Dependencies
# ============================================================================


class TestNoMLDependencies:
    """Verify cluster_classifier has no ML library dependencies (Story 2.3)."""

    def test_module_has_no_sklearn_import(self):
        """Module should not import sklearn."""
        import dedupe.cluster_classifier as cc
        import inspect

        source = inspect.getsource(cc)

        assert 'from sklearn' not in source, "Should not import from sklearn"
        assert 'import sklearn' not in source, "Should not import sklearn"

    def test_module_has_no_kmodes_import(self):
        """Module should not import kmodes."""
        import dedupe.cluster_classifier as cc
        import inspect

        source = inspect.getsource(cc)

        assert 'from kmodes' not in source, "Should not import from kmodes"
        assert 'import kmodes' not in source, "Should not import kmodes"

    def test_module_only_uses_allowed_imports(self):
        """Module should only use standard library + numpy/pandas/yaml."""
        import dedupe.cluster_classifier as cc
        import inspect

        source = inspect.getsource(cc)

        # Extract import lines
        lines = source.split('\n')
        import_lines = [l.strip() for l in lines if l.strip().startswith(('import ', 'from '))]

        # Allowed modules
        allowed_patterns = [
            'pathlib', 'typing', 'collections', 'logging',
            'numpy', 'pandas', 'yaml', 'np', 'pd'
        ]

        for line in import_lines:
            # Check if line contains any disallowed import
            is_allowed = any(pattern in line for pattern in allowed_patterns)
            assert is_allowed, f"Unexpected import: {line}"

    def test_classifier_works_without_ml_libraries(self):
        """Classifier should work without sklearn/kmodes being imported."""
        from dedupe.cluster_classifier import HammingDistanceClassifier

        centroids = {
            0: np.array([1, 1, 1, 1, 1]),
            1: np.array([0, 0, 0, 0, 0]),
        }

        classifier = HammingDistanceClassifier(centroids)

        # Should classify without any ML library
        result = classifier.classify_pair(np.array([1, 1, 1, 0, 0]))
        assert result in [0, 1], "Should return valid cluster"
