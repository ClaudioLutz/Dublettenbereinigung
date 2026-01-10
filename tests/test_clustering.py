"""
Unit tests for k-modes clustering module.

Tests cover:
- K-modes clustering execution
- Silhouette score calculation with Hamming distance
- Cluster profile interpretation
- Clustering quality evaluation
- Model export to YAML (Story 2.1)
"""

import pytest
import numpy as np
import pandas as pd
import yaml
from pathlib import Path
from datetime import date
from dedupe.analysis.clustering import (
    perform_kmodes_clustering,
    validate_k_silhouette,
    get_cluster_profiles,
    interpret_cluster_profile,
    evaluate_clustering_quality
)


@pytest.fixture
def sample_binary_data():
    """Create small synthetic binary dataset for testing."""
    np.random.seed(42)

    # Create 100 samples with 10 binary features
    # Make 3 distinct patterns for clustering
    n_samples = 100
    n_features = 10

    # Pattern 1: First 5 features mostly 1
    pattern1 = np.random.binomial(1, 0.8, size=(33, n_features))
    pattern1[:, :5] = 1
    pattern1[:, 5:] = 0

    # Pattern 2: Last 5 features mostly 1
    pattern2 = np.random.binomial(1, 0.8, size=(33, n_features))
    pattern2[:, :5] = 0
    pattern2[:, 5:] = 1

    # Pattern 3: Middle features mostly 1
    pattern3 = np.random.binomial(1, 0.8, size=(34, n_features))
    pattern3[:, :3] = 0
    pattern3[:, 3:7] = 1
    pattern3[:, 7:] = 0

    data = np.vstack([pattern1, pattern2, pattern3])
    return data


@pytest.fixture
def feature_names():
    """Generate feature names for testing."""
    return [f'feature_{i}' for i in range(10)]


def test_kmodes_on_sample_data(sample_binary_data):
    """Test that k-modes runs without errors on small synthetic dataset."""
    X = sample_binary_data

    # Run k-modes with k=3 (should match our 3 patterns)
    labels, centroids, cost = perform_kmodes_clustering(X, n_clusters=3, random_state=42)

    # Verify outputs
    assert labels is not None
    assert len(labels) == len(X)
    assert centroids is not None
    assert centroids.shape == (3, X.shape[1])
    assert cost >= 0  # Cost should be non-negative (0 = perfect clustering)
    assert len(np.unique(labels)) == 3  # Should have 3 distinct clusters


def test_silhouette_calculation(sample_binary_data):
    """Test that Silhouette score is calculated correctly with Hamming distance."""
    X = sample_binary_data

    # Run Silhouette validation for k=2 to k=5
    results = validate_k_silhouette(X, k_range=range(2, 6))

    # Verify structure
    assert 'silhouette' in results
    assert 'cost' in results

    # Verify k values present
    for k in range(2, 6):
        assert k in results['silhouette']
        assert k in results['cost']

    # Silhouette scores should be in valid range (-1, 1)
    for k, score in results['silhouette'].items():
        assert -1 <= score <= 1, f"Invalid Silhouette score for k={k}: {score}"

    # k=3 should have a good Silhouette score (our data has 3 patterns)
    assert results['silhouette'][3] > 0.3, "k=3 should have decent Silhouette score"


def test_cluster_profile_interpretation(sample_binary_data, feature_names):
    """Test that centroids are converted to readable format."""
    X = sample_binary_data

    # Run k-modes
    labels, centroids, cost = perform_kmodes_clustering(X, n_clusters=3, random_state=42)

    # Get cluster profiles
    profiles_df = get_cluster_profiles(centroids, feature_names)

    # Verify structure
    assert isinstance(profiles_df, pd.DataFrame)
    assert len(profiles_df) == 3  # 3 clusters
    assert 'cluster_id' in profiles_df.columns
    assert 'active_features_count' in profiles_df.columns

    # All feature names should be in columns
    for fname in feature_names:
        assert fname in profiles_df.columns

    # Test interpretation
    for idx, row in profiles_df.iterrows():
        interpretation = interpret_cluster_profile(row, feature_names)
        assert isinstance(interpretation, str)
        assert len(interpretation) > 0
        assert 'Cluster' in interpretation


def test_clustering_quality_evaluation():
    """Test clustering quality assessment based on Silhouette score."""
    # Test different quality levels
    assert "EXCELLENT" in evaluate_clustering_quality(0.75)
    assert "GOOD" in evaluate_clustering_quality(0.55)
    assert "ACCEPTABLE" in evaluate_clustering_quality(0.35)
    assert "POOR" in evaluate_clustering_quality(0.15)
    assert "INVALID" in evaluate_clustering_quality(-0.5)


def test_kmodes_with_edge_cases():
    """Test k-modes with edge cases."""
    # Test with k=1 (single cluster)
    X = np.random.binomial(1, 0.5, size=(50, 10))
    labels, centroids, cost = perform_kmodes_clustering(X, n_clusters=1, random_state=42)
    assert len(np.unique(labels)) == 1
    assert all(labels == 0)

    # Test with k > n_samples (should handle gracefully or raise error)
    # Note: k-modes may not handle this well, so we expect an exception
    with pytest.raises(Exception):
        perform_kmodes_clustering(X, n_clusters=100, random_state=42)


def test_feature_extraction_consistency():
    """Test that feature extraction is deterministic with same random_state."""
    X = np.random.binomial(1, 0.5, size=(100, 10))

    # Run twice with same random_state
    labels1, _, _ = perform_kmodes_clustering(X, n_clusters=5, random_state=42)
    labels2, _, _ = perform_kmodes_clustering(X, n_clusters=5, random_state=42)

    # Should get identical results
    assert np.array_equal(labels1, labels2), "Results should be deterministic with same random_state"


def test_hamming_distance_metric():
    """Test that Hamming distance is used correctly for binary data."""
    # Create simple binary data where Hamming distance is obvious
    X = np.array([
        [1, 1, 1, 0, 0],
        [1, 1, 1, 0, 0],
        [0, 0, 0, 1, 1],
        [0, 0, 0, 1, 1],
    ])

    # With k=2, should cleanly separate into 2 groups
    labels, centroids, cost = perform_kmodes_clustering(X, n_clusters=2, random_state=42)

    # Verify that samples [0,1] are in same cluster and [2,3] are in same cluster
    assert labels[0] == labels[1], "Identical samples should be in same cluster"
    assert labels[2] == labels[3], "Identical samples should be in same cluster"
    assert labels[0] != labels[2], "Different samples should be in different clusters"

    # Cost should be 0 (perfect clustering)
    assert cost == 0.0, "Cost should be 0 for perfect clustering"


# ============================================================================
# Story 2.1: Export K-Modes Cluster Model to YAML Format
# ============================================================================


class TestModelExport:
    """Test model export functionality (Story 2.1)."""

    @pytest.fixture
    def sample_centroids(self):
        """Create sample centroids for testing export."""
        return np.array([
            [1, 0, 1, 0, 1],
            [0, 1, 0, 1, 0],
            [1, 1, 1, 0, 0],
        ])

    @pytest.fixture
    def sample_feature_names(self):
        """Create sample feature names for testing."""
        return ['feature_0', 'feature_1', 'feature_2', 'feature_3', 'feature_4']

    def test_export_creates_yaml_file(self, sample_centroids, sample_feature_names, tmp_path):
        """Export should create a valid YAML file."""
        from dedupe.analysis.clustering import export_cluster_model

        output_path = tmp_path / "cluster_model_v1.yaml"

        export_cluster_model(
            centroids=sample_centroids,
            feature_names=sample_feature_names,
            output_path=output_path,
            model_version="v1"
        )

        assert output_path.exists(), "YAML file should be created"
        assert output_path.stat().st_size > 0, "File should not be empty"

    def test_export_yaml_contains_required_keys(self, sample_centroids, sample_feature_names, tmp_path):
        """Exported YAML should contain all required keys."""
        from dedupe.analysis.clustering import export_cluster_model

        output_path = tmp_path / "cluster_model_v1.yaml"

        export_cluster_model(
            centroids=sample_centroids,
            feature_names=sample_feature_names,
            output_path=output_path,
            model_version="v1",
            silhouette_score=0.42
        )

        with open(output_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Check required keys
        assert 'version' in config, "Should have 'version' key"
        assert 'model_version' in config, "Should have 'model_version' key"
        assert 'n_clusters' in config, "Should have 'n_clusters' key"
        assert 'n_features' in config, "Should have 'n_features' key"
        assert 'feature_names' in config, "Should have 'feature_names' key"
        assert 'centroids' in config, "Should have 'centroids' key"

    def test_export_yaml_contains_metadata(self, sample_centroids, sample_feature_names, tmp_path):
        """Exported YAML should contain metadata."""
        from dedupe.analysis.clustering import export_cluster_model

        output_path = tmp_path / "cluster_model_v1.yaml"

        export_cluster_model(
            centroids=sample_centroids,
            feature_names=sample_feature_names,
            output_path=output_path,
            model_version="v1",
            silhouette_score=0.42,
            validation_date="2026-01-08"
        )

        with open(output_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Check metadata
        assert 'created_date' in config, "Should have 'created_date' key"
        assert 'silhouette_score' in config, "Should have 'silhouette_score' key"
        assert config['silhouette_score'] == 0.42, "Silhouette score should match"
        assert config['model_version'] == "v1", "Model version should match"

    def test_export_centroids_are_binary(self, sample_centroids, sample_feature_names, tmp_path):
        """Exported centroids should contain only 0 or 1 values."""
        from dedupe.analysis.clustering import export_cluster_model

        output_path = tmp_path / "cluster_model_v1.yaml"

        export_cluster_model(
            centroids=sample_centroids,
            feature_names=sample_feature_names,
            output_path=output_path,
            model_version="v1"
        )

        with open(output_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        for cluster_id, centroid in config['centroids'].items():
            for value in centroid:
                assert value in [0, 1], f"Centroid values should be binary, got {value}"

    def test_export_dimensions_match(self, sample_centroids, sample_feature_names, tmp_path):
        """Exported dimensions should match input."""
        from dedupe.analysis.clustering import export_cluster_model

        output_path = tmp_path / "cluster_model_v1.yaml"

        export_cluster_model(
            centroids=sample_centroids,
            feature_names=sample_feature_names,
            output_path=output_path,
            model_version="v1"
        )

        with open(output_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        assert config['n_clusters'] == 3, "Should have 3 clusters"
        assert config['n_features'] == 5, "Should have 5 features"
        assert len(config['feature_names']) == 5, "Should have 5 feature names"
        assert len(config['centroids']) == 3, "Should have 3 centroid entries"

        # Each centroid should have 5 values
        for cluster_id, centroid in config['centroids'].items():
            assert len(centroid) == 5, f"Centroid {cluster_id} should have 5 values"

    def test_export_yaml_is_valid(self, sample_centroids, sample_feature_names, tmp_path):
        """Exported YAML should parse without errors."""
        from dedupe.analysis.clustering import export_cluster_model

        output_path = tmp_path / "cluster_model_v1.yaml"

        export_cluster_model(
            centroids=sample_centroids,
            feature_names=sample_feature_names,
            output_path=output_path,
            model_version="v1"
        )

        # Should not raise any exceptions
        with open(output_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        assert config is not None, "YAML should parse to valid object"


class TestModelSchemaValidation:
    """Test model schema validation (Story 2.1)."""

    def test_validate_schema_valid_model(self, tmp_path):
        """Valid model should pass validation."""
        from dedupe.analysis.clustering import validate_model_schema

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
  0: [1, 0, 1, 0, 1]
  1: [0, 1, 0, 1, 0]
  2: [1, 1, 1, 0, 0]
"""
        config_path = tmp_path / "valid_model.yaml"
        config_path.write_text(yaml_content, encoding='utf-8')

        # Should not raise exception
        is_valid = validate_model_schema(config_path)
        assert is_valid is True, "Valid schema should pass validation"

    def test_validate_schema_missing_centroids(self, tmp_path):
        """Missing centroids should fail validation."""
        from dedupe.analysis.clustering import validate_model_schema

        yaml_content = """
version: "1.0"
model_version: "v1"
n_clusters: 3
n_features: 5
feature_names:
  - f0
  - f1
  - f2
  - f3
  - f4
"""
        config_path = tmp_path / "invalid_model.yaml"
        config_path.write_text(yaml_content, encoding='utf-8')

        with pytest.raises(ValueError, match="centroids"):
            validate_model_schema(config_path)

    def test_validate_schema_dimension_mismatch(self, tmp_path):
        """Centroid dimension mismatch should fail validation."""
        from dedupe.analysis.clustering import validate_model_schema

        yaml_content = """
version: "1.0"
model_version: "v1"
n_clusters: 3
n_features: 5
feature_names:
  - f0
  - f1
  - f2
  - f3
  - f4
centroids:
  0: [1, 0, 1]  # Only 3 values, should be 5
  1: [0, 1, 0, 1, 0]
  2: [1, 1, 1, 0, 0]
"""
        config_path = tmp_path / "mismatch_model.yaml"
        config_path.write_text(yaml_content, encoding='utf-8')

        with pytest.raises(ValueError, match="dimension"):
            validate_model_schema(config_path)


class TestVersionedFilename:
    """Test versioned filename generation (Story 2.1)."""

    def test_get_next_model_version_empty_dir(self, tmp_path):
        """Empty directory should return v1."""
        from dedupe.analysis.clustering import get_next_model_version

        version = get_next_model_version(tmp_path)
        assert version == "v1", "First version should be v1"

    def test_get_next_model_version_with_existing(self, tmp_path):
        """Should return next version after existing models."""
        from dedupe.analysis.clustering import get_next_model_version

        # Create existing model files
        (tmp_path / "cluster_model_v1.yaml").touch()
        (tmp_path / "cluster_model_v2.yaml").touch()

        version = get_next_model_version(tmp_path)
        assert version == "v3", "Should return v3 after v1 and v2 exist"

    def test_get_next_model_version_with_gaps(self, tmp_path):
        """Should return next version after highest, even with gaps."""
        from dedupe.analysis.clustering import get_next_model_version

        # Create non-contiguous versions
        (tmp_path / "cluster_model_v1.yaml").touch()
        (tmp_path / "cluster_model_v5.yaml").touch()

        version = get_next_model_version(tmp_path)
        assert version == "v6", "Should return v6 after v5 (highest)"
