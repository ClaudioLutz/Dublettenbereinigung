"""
Unit tests for tiered output generation (Story 1.1).

Tests the tier assignment logic that separates pairs into:
- Tier 1 (auto-merge): Clusters with 0% FP rate
- Tier 2 (review queue): Clusters with >0% FP rate
"""

import pytest
import pandas as pd
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCalculateFPRates:
    """Test false positive rate calculation per cluster."""

    def test_zero_fp_cluster_all_duplicates(self):
        """Cluster with all DUPLICATE labels should have 0% FP rate."""
        df = pd.DataFrame({
            'cluster': [0, 0, 0, 0],
            'llm_label': ['DUPLICATE', 'DUPLICATE', 'DUPLICATE', 'DUPLICATE']
        })

        from scripts.generate_tiered_output import calculate_cluster_fp_rates
        fp_rates = calculate_cluster_fp_rates(df)

        assert fp_rates[0] == 0.0, "Cluster with all DUPLICATE should have 0% FP"

    def test_nonzero_fp_cluster_with_one_not_duplicate(self):
        """Cluster with one NOT_DUPLICATE should have >0% FP rate."""
        df = pd.DataFrame({
            'cluster': [1, 1, 1, 1],
            'llm_label': ['DUPLICATE', 'NOT_DUPLICATE', 'DUPLICATE', 'DUPLICATE']
        })

        from scripts.generate_tiered_output import calculate_cluster_fp_rates
        fp_rates = calculate_cluster_fp_rates(df)

        assert fp_rates[1] == 25.0, "1 NOT_DUPLICATE out of 4 = 25% FP"

    def test_multiple_clusters_different_fp_rates(self):
        """Test multiple clusters with varying FP rates."""
        df = pd.DataFrame({
            'cluster': [0, 0, 0, 1, 1, 1, 1, 2, 2],
            'llm_label': [
                'DUPLICATE', 'DUPLICATE', 'DUPLICATE',  # Cluster 0: 0% FP
                'DUPLICATE', 'NOT_DUPLICATE', 'DUPLICATE', 'DUPLICATE',  # Cluster 1: 25% FP
                'NOT_DUPLICATE', 'NOT_DUPLICATE'  # Cluster 2: 100% FP
            ]
        })

        from scripts.generate_tiered_output import calculate_cluster_fp_rates
        fp_rates = calculate_cluster_fp_rates(df)

        assert fp_rates[0] == 0.0, "Cluster 0: 0% FP"
        assert fp_rates[1] == 25.0, "Cluster 1: 25% FP"
        assert fp_rates[2] == 100.0, "Cluster 2: 100% FP"

    def test_empty_cluster_handling(self):
        """Empty DataFrame should return empty FP rates dict."""
        df = pd.DataFrame({'cluster': [], 'llm_label': []})

        from scripts.generate_tiered_output import calculate_cluster_fp_rates
        fp_rates = calculate_cluster_fp_rates(df)

        assert fp_rates == {}, "Empty DataFrame should return empty dict"


class TestClassifyTiers:
    """Test tier classification logic."""

    def test_classify_tiers_separates_by_fp_rate(self):
        """Tier 1 should contain only 0% FP clusters, Tier 2 the rest."""
        df = pd.DataFrame({
            'i': [1, 2, 3, 4],
            'j': [10, 20, 30, 40],
            'cluster': [0, 0, 1, 1],
            'score': [80.0, 85.0, 60.0, 65.0]
        })
        fp_rates = {0: 0.0, 1: 15.0}

        from scripts.generate_tiered_output import classify_tiers
        tier1, tier2 = classify_tiers(df, fp_rates, tier1_threshold=0.0)

        assert len(tier1) == 2, "Tier 1 should have 2 pairs from cluster 0 (0% FP)"
        assert len(tier2) == 2, "Tier 2 should have 2 pairs from cluster 1 (15% FP)"
        assert all(tier1['cluster'] == 0), "All Tier 1 pairs should be from cluster 0"
        assert all(tier2['cluster'] == 1), "All Tier 2 pairs should be from cluster 1"

    def test_classify_tiers_all_zero_fp(self):
        """All clusters with 0% FP should go to Tier 1."""
        df = pd.DataFrame({
            'i': [1, 2, 3, 4],
            'j': [10, 20, 30, 40],
            'cluster': [0, 0, 1, 1],
            'score': [80.0, 85.0, 60.0, 65.0]
        })
        fp_rates = {0: 0.0, 1: 0.0}

        from scripts.generate_tiered_output import classify_tiers
        tier1, tier2 = classify_tiers(df, fp_rates, tier1_threshold=0.0)

        assert len(tier1) == 4, "All pairs should be in Tier 1 (all 0% FP)"
        assert len(tier2) == 0, "Tier 2 should be empty"

    def test_classify_tiers_all_nonzero_fp(self):
        """All clusters with >0% FP should go to Tier 2."""
        df = pd.DataFrame({
            'i': [1, 2, 3, 4],
            'j': [10, 20, 30, 40],
            'cluster': [0, 0, 1, 1],
            'score': [80.0, 85.0, 60.0, 65.0]
        })
        fp_rates = {0: 10.0, 1: 15.0}

        from scripts.generate_tiered_output import classify_tiers
        tier1, tier2 = classify_tiers(df, fp_rates, tier1_threshold=0.0)

        assert len(tier1) == 0, "Tier 1 should be empty (no 0% FP clusters)"
        assert len(tier2) == 4, "All pairs should be in Tier 2"

    def test_classify_tiers_preserves_original_columns(self):
        """Tier outputs should preserve all original columns."""
        df = pd.DataFrame({
            'i': [1, 2],
            'j': [10, 20],
            'cluster': [0, 0],
            'score': [80.0, 85.0],
            'vorname_i': ['Anna', 'Beat'],
            'name_i': ['Muller', 'Schmidt']
        })
        fp_rates = {0: 0.0}

        from scripts.generate_tiered_output import classify_tiers
        tier1, tier2 = classify_tiers(df, fp_rates, tier1_threshold=0.0)

        expected_cols = ['i', 'j', 'cluster', 'score', 'vorname_i', 'name_i']
        assert list(tier1.columns) == expected_cols, "Tier 1 should preserve all columns"


class TestValidateClusterRange:
    """Test cluster range validation (AC5)."""

    def test_valid_cluster_range(self):
        """Clusters in valid range (0-14) should pass validation."""
        df = pd.DataFrame({'cluster': [0, 5, 10, 14]})

        from scripts.generate_tiered_output import validate_cluster_range

        # Should not raise exception
        validate_cluster_range(df)

    def test_invalid_cluster_below_minimum(self):
        """Cluster value below minimum should raise ValueError."""
        df = pd.DataFrame({'cluster': [0, 5, -1]})

        from scripts.generate_tiered_output import validate_cluster_range

        with pytest.raises(ValueError, match="Invalid cluster values"):
            validate_cluster_range(df)

    def test_invalid_cluster_above_maximum(self):
        """Cluster value above maximum should raise ValueError."""
        df = pd.DataFrame({'cluster': [0, 5, 15]})

        from scripts.generate_tiered_output import validate_cluster_range

        with pytest.raises(ValueError, match="Invalid cluster values"):
            validate_cluster_range(df)

    def test_custom_cluster_range(self):
        """Custom min/max cluster range should be respected."""
        df = pd.DataFrame({'cluster': [0, 1, 2]})

        from scripts.generate_tiered_output import validate_cluster_range

        # Should pass with custom range
        validate_cluster_range(df, min_cluster=0, max_cluster=5)

        # Should fail with stricter range
        with pytest.raises(ValueError, match="Invalid cluster values"):
            validate_cluster_range(df, min_cluster=0, max_cluster=1)


class TestDataIntegrityValidation:
    """Test data integrity validation."""

    def test_validate_no_data_loss(self):
        """Validation should pass when total pairs match."""
        original_df = pd.DataFrame({'i': [1, 2, 3], 'j': [10, 20, 30]})
        tier1_df = pd.DataFrame({'i': [1, 2], 'j': [10, 20]})
        tier2_df = pd.DataFrame({'i': [3], 'j': [30]})

        from scripts.generate_tiered_output import validate_tier_integrity

        # Should not raise exception
        validate_tier_integrity(original_df, tier1_df, tier2_df)

    def test_validate_detects_data_loss(self):
        """Validation should fail when pairs are missing."""
        original_df = pd.DataFrame({'i': [1, 2, 3], 'j': [10, 20, 30]})
        tier1_df = pd.DataFrame({'i': [1, 2], 'j': [10, 20]})
        tier2_df = pd.DataFrame({'i': [], 'j': []})  # Missing pair 3

        from scripts.generate_tiered_output import validate_tier_integrity

        with pytest.raises(AssertionError, match="Data loss detected"):
            validate_tier_integrity(original_df, tier1_df, tier2_df)

    def test_validate_detects_duplicates_across_tiers(self):
        """Validation should fail when same pair appears in both tiers."""
        original_df = pd.DataFrame({'i': [1, 2], 'j': [10, 20]})
        tier1_df = pd.DataFrame({'i': [1], 'j': [10]})
        tier2_df = pd.DataFrame({'i': [1, 2], 'j': [10, 20]})  # Pair 1 duplicated

        from scripts.generate_tiered_output import validate_tier_integrity

        with pytest.raises(AssertionError, match="Duplicate pairs found"):
            validate_tier_integrity(original_df, tier1_df, tier2_df)


class TestReorderColumnsForAC4:
    """Test column reordering per AC4 specification."""

    def test_reorder_columns_correct_order(self):
        """Columns should be reordered to: match_id, cluster, confidence, i, j, ..."""
        df = pd.DataFrame({
            'i': [1, 2],
            'j': [10, 20],
            'cluster': [0, 1],
            'confidence': [80.0, 85.0],
            'match_id': ['1_10', '2_20'],
            'name_i': ['Anna', 'Beat']
        })

        from scripts.generate_tiered_output import reorder_columns_for_ac4
        result = reorder_columns_for_ac4(df)

        expected_order = ['match_id', 'cluster', 'confidence', 'i', 'j', 'name_i']
        assert list(result.columns) == expected_order, "Columns should be reordered per AC4"

    def test_reorder_preserves_all_columns(self):
        """All original columns should be preserved after reordering."""
        df = pd.DataFrame({
            'extra_col': ['x', 'y'],
            'i': [1, 2],
            'j': [10, 20],
            'cluster': [0, 1],
            'confidence': [80.0, 85.0],
            'match_id': ['1_10', '2_20'],
            'another_col': ['a', 'b']
        })

        from scripts.generate_tiered_output import reorder_columns_for_ac4
        result = reorder_columns_for_ac4(df)

        assert len(result.columns) == len(df.columns), "All columns should be preserved"
        assert set(result.columns) == set(df.columns), "Column names should match"


class TestLoadClusteredResults:
    """Test load_clustered_results function."""

    def test_load_file_not_found_clustered(self, tmp_path):
        """Should raise FileNotFoundError if clustered_results.csv doesn't exist."""
        from scripts.generate_tiered_output import load_clustered_results

        with pytest.raises(FileNotFoundError, match="File not found"):
            load_clustered_results(
                tmp_path / "nonexistent.csv",
                tmp_path / "llm_labeled.csv"
            )

    def test_load_file_not_found_llm(self, tmp_path):
        """Should raise FileNotFoundError if llm_labeled_results.csv doesn't exist."""
        from scripts.generate_tiered_output import load_clustered_results

        # Create clustered file but not LLM file
        clustered_path = tmp_path / "clustered.csv"
        df = pd.DataFrame({'i': [1], 'j': [2], 'score': [80.0], 'cluster': [0]})
        df.to_csv(clustered_path, index=False)

        with pytest.raises(FileNotFoundError, match="File not found"):
            load_clustered_results(
                clustered_path,
                tmp_path / "nonexistent_llm.csv"
            )

    def test_load_missing_required_columns_clustered(self, tmp_path):
        """Should raise ValueError if clustered file missing required columns."""
        from scripts.generate_tiered_output import load_clustered_results

        clustered_path = tmp_path / "clustered.csv"
        llm_path = tmp_path / "llm.csv"

        # Missing 'score' column
        pd.DataFrame({'i': [1], 'j': [2], 'cluster': [0]}).to_csv(clustered_path, index=False)
        pd.DataFrame({'i': [1], 'j': [2], 'cluster': [0], 'llm_label': ['DUPLICATE']}).to_csv(llm_path, index=False)

        with pytest.raises(ValueError, match="Missing required columns"):
            load_clustered_results(clustered_path, llm_path)

    def test_load_missing_required_columns_llm(self, tmp_path):
        """Should raise ValueError if LLM file missing required columns."""
        from scripts.generate_tiered_output import load_clustered_results

        clustered_path = tmp_path / "clustered.csv"
        llm_path = tmp_path / "llm.csv"

        pd.DataFrame({'i': [1], 'j': [2], 'score': [80.0], 'cluster': [0]}).to_csv(clustered_path, index=False)
        # Missing 'llm_label' column
        pd.DataFrame({'i': [1], 'j': [2], 'cluster': [0]}).to_csv(llm_path, index=False)

        with pytest.raises(ValueError, match="Missing required columns"):
            load_clustered_results(clustered_path, llm_path)

    def test_load_successful_returns_tuple(self, tmp_path):
        """Successful load should return tuple of (DataFrame, Dict)."""
        from scripts.generate_tiered_output import load_clustered_results

        clustered_path = tmp_path / "clustered.csv"
        llm_path = tmp_path / "llm.csv"

        pd.DataFrame({
            'i': [1, 2], 'j': [10, 20], 'score': [80.0, 85.0], 'cluster': [0, 0]
        }).to_csv(clustered_path, index=False)
        pd.DataFrame({
            'i': [1], 'j': [10], 'cluster': [0], 'llm_label': ['DUPLICATE']
        }).to_csv(llm_path, index=False)

        result = load_clustered_results(clustered_path, llm_path)

        assert isinstance(result, tuple), "Should return tuple"
        assert len(result) == 2, "Tuple should have 2 elements"
        assert isinstance(result[0], pd.DataFrame), "First element should be DataFrame"
        assert isinstance(result[1], dict), "Second element should be dict"


class TestFindLatestRunDirectory:
    """Test find_latest_run_directory function."""

    def test_find_no_analysis_directory(self, tmp_path):
        """Should raise FileNotFoundError if analysis directory doesn't exist."""
        from scripts.generate_tiered_output import find_latest_run_directory

        with pytest.raises(FileNotFoundError, match="Analysis directory not found"):
            find_latest_run_directory(tmp_path / "nonexistent")

    def test_find_no_run_directories(self, tmp_path):
        """Should raise FileNotFoundError if no run_* directories exist."""
        from scripts.generate_tiered_output import find_latest_run_directory

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="No run directories found"):
            find_latest_run_directory(analysis_dir)

    def test_find_latest_run_directory(self, tmp_path):
        """Should return the most recent run directory (by name sort)."""
        from scripts.generate_tiered_output import find_latest_run_directory

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Create run directories
        (analysis_dir / "run_20260101_100000").mkdir()
        (analysis_dir / "run_20260108_124349").mkdir()
        (analysis_dir / "run_20260105_000000").mkdir()

        result = find_latest_run_directory(analysis_dir)

        assert result.name == "run_20260108_124349", "Should return latest run directory"


class TestCSVEncoding:
    """Test CSV encoding with UTF-8 BOM for Excel compatibility."""

    def test_save_with_bom_creates_file(self, tmp_path):
        """Should save CSV with UTF-8 BOM encoding."""
        df = pd.DataFrame({
            'vorname': ['Muller', 'Schafer'],
            'ort': ['Zurich', 'Geneve']
        })
        output_path = tmp_path / "test_output.csv"

        from scripts.generate_tiered_output import save_with_bom
        save_with_bom(df, output_path)

        assert output_path.exists(), "Output file should exist"

        # Read file and check BOM is present
        with open(output_path, 'rb') as f:
            first_bytes = f.read(3)
            assert first_bytes == b'\xef\xbb\xbf', "File should start with UTF-8 BOM"


# Story 1.2: YAML Configuration Loading Tests
class TestLoadClusterTierMapping:
    """Test cluster-to-tier mapping loading from YAML (Story 1.2)."""

    def test_load_valid_yaml(self, tmp_path):
        """Should successfully load valid YAML configuration."""
        from scripts.generate_tiered_output import load_cluster_tier_mapping

        config_path = tmp_path / "cluster_labels.yaml"
        config_content = """
version: "1.0"
cluster_tiers:
  0: 2
  1: 2
  2: 2
  3: 1
  4: 1
  5: 2
  6: 1
  7: 1
  8: 1
  9: 1
  10: 1
  11: 1
  12: 1
  13: 1
  14: 1
"""
        config_path.write_text(config_content, encoding='utf-8')

        result = load_cluster_tier_mapping(config_path)

        assert isinstance(result, dict), "Should return dictionary"
        assert len(result) == 15, "Should have 15 cluster mappings"
        assert result[0] == 2, "Cluster 0 should map to Tier 2"
        assert result[3] == 1, "Cluster 3 should map to Tier 1"

    def test_load_missing_file_returns_defaults(self, tmp_path):
        """Missing file should return default mapping (all Tier 2)."""
        from scripts.generate_tiered_output import load_cluster_tier_mapping

        result = load_cluster_tier_mapping(tmp_path / "nonexistent.yaml")

        assert isinstance(result, dict), "Should return dictionary"
        assert len(result) == 15, "Should have 15 cluster mappings"
        assert all(tier == 2 for tier in result.values()), "All clusters should default to Tier 2"

    def test_load_missing_clusters_fills_defaults(self, tmp_path):
        """Missing clusters should be filled with default tier."""
        from scripts.generate_tiered_output import load_cluster_tier_mapping

        config_path = tmp_path / "partial_config.yaml"
        config_content = """
version: "1.0"
cluster_tiers:
  0: 1
  1: 2
  # Missing clusters 2-14
"""
        config_path.write_text(config_content, encoding='utf-8')

        result = load_cluster_tier_mapping(config_path)

        assert len(result) == 15, "Should have 15 cluster mappings"
        assert result[0] == 1, "Cluster 0 should be from config"
        assert result[1] == 2, "Cluster 1 should be from config"
        assert result[2] == 2, "Cluster 2 should default to Tier 2"
        assert result[14] == 2, "Cluster 14 should default to Tier 2"

    def test_load_invalid_yaml_syntax(self, tmp_path):
        """Invalid YAML syntax should raise ValueError."""
        from scripts.generate_tiered_output import load_cluster_tier_mapping

        config_path = tmp_path / "invalid.yaml"
        config_path.write_text("invalid: yaml: syntax: [", encoding='utf-8')

        with pytest.raises(ValueError, match="Invalid YAML"):
            load_cluster_tier_mapping(config_path)

    def test_load_missing_cluster_tiers_key(self, tmp_path):
        """YAML without cluster_tiers key should raise ValueError."""
        from scripts.generate_tiered_output import load_cluster_tier_mapping

        config_path = tmp_path / "wrong_schema.yaml"
        config_content = """
version: "1.0"
wrong_key:
  0: 1
"""
        config_path.write_text(config_content, encoding='utf-8')

        with pytest.raises(ValueError, match="missing 'cluster_tiers'"):
            load_cluster_tier_mapping(config_path)

    def test_load_returns_tier1_and_tier2_clusters(self, tmp_path):
        """Should correctly identify Tier 1 and Tier 2 clusters."""
        from scripts.generate_tiered_output import load_cluster_tier_mapping

        config_path = tmp_path / "cluster_labels.yaml"
        config_content = """
version: "1.0"
cluster_tiers:
  0: 2
  1: 2
  2: 2
  3: 1
  4: 1
  5: 2
  6: 1
  7: 1
  8: 1
  9: 1
  10: 1
  11: 1
  12: 1
  13: 1
  14: 1
"""
        config_path.write_text(config_content, encoding='utf-8')

        result = load_cluster_tier_mapping(config_path)

        tier1_clusters = [c for c, t in result.items() if t == 1]
        tier2_clusters = [c for c, t in result.items() if t == 2]

        assert tier1_clusters == [3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14], "Tier 1 clusters should match"
        assert tier2_clusters == [0, 1, 2, 5], "Tier 2 clusters should match"


class TestClassifyTiersWithMapping:
    """Test tier classification using YAML mapping (Story 1.2)."""

    def test_classify_with_mapping_tier1(self):
        """Should classify pairs to Tier 1 based on cluster mapping."""
        from scripts.generate_tiered_output import classify_tiers_with_mapping

        df = pd.DataFrame({
            'i': [1, 2, 3, 4],
            'j': [10, 20, 30, 40],
            'cluster': [3, 4, 0, 1],  # 3,4 -> Tier 1; 0,1 -> Tier 2
            'score': [80.0, 85.0, 60.0, 65.0]
        })
        cluster_tier_mapping = {0: 2, 1: 2, 2: 2, 3: 1, 4: 1, 5: 2}

        tier1, tier2 = classify_tiers_with_mapping(df, cluster_tier_mapping)

        assert len(tier1) == 2, "Tier 1 should have 2 pairs (clusters 3, 4)"
        assert len(tier2) == 2, "Tier 2 should have 2 pairs (clusters 0, 1)"
        assert set(tier1['cluster']) == {3, 4}, "Tier 1 clusters should be 3, 4"
        assert set(tier2['cluster']) == {0, 1}, "Tier 2 clusters should be 0, 1"

    def test_classify_with_mapping_all_tier2(self):
        """All Tier 2 mapping should put all pairs in Tier 2."""
        from scripts.generate_tiered_output import classify_tiers_with_mapping

        df = pd.DataFrame({
            'i': [1, 2, 3],
            'j': [10, 20, 30],
            'cluster': [0, 1, 2],
            'score': [80.0, 85.0, 60.0]
        })
        cluster_tier_mapping = {0: 2, 1: 2, 2: 2}

        tier1, tier2 = classify_tiers_with_mapping(df, cluster_tier_mapping)

        assert len(tier1) == 0, "Tier 1 should be empty"
        assert len(tier2) == 3, "All pairs should be in Tier 2"

    def test_classify_with_mapping_preserves_columns(self):
        """Classification should preserve all original columns."""
        from scripts.generate_tiered_output import classify_tiers_with_mapping

        df = pd.DataFrame({
            'i': [1, 2],
            'j': [10, 20],
            'cluster': [3, 0],
            'score': [80.0, 85.0],
            'vorname_i': ['Anna', 'Beat'],
            'extra_col': ['x', 'y']
        })
        cluster_tier_mapping = {0: 2, 3: 1}

        tier1, tier2 = classify_tiers_with_mapping(df, cluster_tier_mapping)

        assert list(tier1.columns) == list(df.columns), "Tier 1 columns should match input"
        assert list(tier2.columns) == list(df.columns), "Tier 2 columns should match input"


# Story 1.4: Tier Assignment Validation Report Tests
class TestGenerateTierReport:
    """Test tier report generation (Story 1.4)."""

    @pytest.fixture
    def sample_tier_stats(self):
        """Create sample tier statistics for testing."""
        return {
            'total_pairs': 78677,
            'tier1_count': 20619,
            'tier2_count': 58058,
            'tier1_pct': 26.2,
            'tier2_pct': 73.8,
            'validation_date': '2026-01-08',
            'model_version': 'cluster_model_v1',
        }

    @pytest.fixture
    def sample_cluster_stats(self):
        """Create sample cluster statistics."""
        return {
            0: {'count': 12456, 'fp_rate': 15.2, 'tier': 2},
            1: {'count': 8234, 'fp_rate': 8.7, 'tier': 2},
            2: {'count': 7891, 'fp_rate': 12.3, 'tier': 2},
            3: {'count': 5234, 'fp_rate': 0.0, 'tier': 1},
            4: {'count': 3891, 'fp_rate': 0.0, 'tier': 1},
            5: {'count': 4567, 'fp_rate': 5.1, 'tier': 2},
        }

    def test_generate_report_creates_markdown(self, sample_tier_stats, sample_cluster_stats):
        """Report should be valid Markdown format."""
        from scripts.generate_tiered_output import generate_tier_report

        report = generate_tier_report(sample_tier_stats, sample_cluster_stats)

        assert '# Tier Assignment Validation Report' in report
        assert '## Summary' in report
        assert '## Cluster Distribution' in report

    def test_generate_report_includes_summary_stats(self, sample_tier_stats, sample_cluster_stats):
        """Report should include tier statistics."""
        from scripts.generate_tiered_output import generate_tier_report

        report = generate_tier_report(sample_tier_stats, sample_cluster_stats)

        assert '78,677' in report or '78677' in report, "Should include total pairs"
        assert '20,619' in report or '20619' in report, "Should include Tier 1 count"
        assert '26.2%' in report or '26.2' in report, "Should include Tier 1 percentage"

    def test_generate_report_includes_cluster_distribution(self, sample_tier_stats, sample_cluster_stats):
        """Report should include cluster distribution."""
        from scripts.generate_tiered_output import generate_tier_report

        report = generate_tier_report(sample_tier_stats, sample_cluster_stats)

        assert 'Tier 1' in report, "Should mention Tier 1"
        assert 'Tier 2' in report, "Should mention Tier 2"
        assert '0.0%' in report, "Should include 0% FP clusters"
        assert '15.2%' in report or '15.2' in report, "Should include non-zero FP rates"

    def test_generate_report_includes_validation_metadata(self, sample_tier_stats, sample_cluster_stats):
        """Report should include validation metadata."""
        from scripts.generate_tiered_output import generate_tier_report

        report = generate_tier_report(sample_tier_stats, sample_cluster_stats)

        assert '2026-01-08' in report, "Should include validation date"
        assert 'cluster_model_v1' in report, "Should include model version"


class TestCalculateTierStats:
    """Test tier statistics calculation."""

    def test_calculate_tier_stats(self):
        """Should calculate correct tier statistics."""
        from scripts.generate_tiered_output import calculate_tier_stats

        tier1_df = pd.DataFrame({'i': range(20), 'j': range(20, 40)})
        tier2_df = pd.DataFrame({'i': range(80), 'j': range(80, 160)})

        stats = calculate_tier_stats(tier1_df, tier2_df)

        assert stats['tier1_count'] == 20
        assert stats['tier2_count'] == 80
        assert stats['total_pairs'] == 100
        assert stats['tier1_pct'] == 20.0
        assert stats['tier2_pct'] == 80.0

    def test_calculate_cluster_stats(self):
        """Should calculate correct cluster statistics."""
        from scripts.generate_tiered_output import calculate_cluster_stats

        clustered_df = pd.DataFrame({
            'cluster': [0, 0, 0, 1, 1, 2],
            'i': range(6),
            'j': range(6, 12)
        })
        fp_rates = {0: 15.2, 1: 0.0, 2: 8.7}
        cluster_tier_mapping = {0: 2, 1: 1, 2: 2}

        stats = calculate_cluster_stats(clustered_df, fp_rates, cluster_tier_mapping)

        assert stats[0]['count'] == 3
        assert stats[0]['fp_rate'] == 15.2
        assert stats[0]['tier'] == 2
        assert stats[1]['count'] == 2
        assert stats[1]['tier'] == 1


class TestSaveTierReport:
    """Test saving tier report to file."""

    def test_save_tier_report(self, tmp_path):
        """Should save report to specified path."""
        from scripts.generate_tiered_output import save_tier_report

        report_content = "# Test Report\n\nThis is a test."
        report_path = tmp_path / "tier_report.md"

        save_tier_report(report_content, report_path)

        assert report_path.exists(), "Report file should exist"
        saved_content = report_path.read_text(encoding='utf-8')
        assert saved_content == report_content, "Content should match"
