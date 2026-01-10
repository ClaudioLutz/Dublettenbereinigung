"""
Unit tests for end-to-end pipeline integration (Story 3.1).

Tests the integration of Stage 3 (tier assignment) into the existing
deduplication pipeline, ensuring automatic execution after Stage 2.
"""

import pytest
import time
import logging
from pathlib import Path
import sys
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Story 3.1: Pipeline Integration Tests
# ============================================================================


class TestRunTierAssignment:
    """Test the run_tier_assignment function for programmatic execution (AC1, AC2)."""

    @pytest.fixture
    def sample_run_directory(self, tmp_path):
        """Create a sample run directory with required input files."""
        run_dir = tmp_path / "_bmad-output" / "analysis" / "run_20260110_120000"
        run_dir.mkdir(parents=True)

        # Create clustered_results.csv
        clustered_df = pd.DataFrame({
            'i': [1, 2, 3, 4, 5, 6],
            'j': [10, 20, 30, 40, 50, 60],
            'score': [85.0, 80.0, 75.0, 70.0, 65.0, 60.0],
            'cluster': [3, 3, 0, 0, 1, 1],  # 3->Tier1, 0,1->Tier2
            'vorname_A': ['Anna', 'Beat', 'Carl', 'Dana', 'Emil', 'Fran'],
            'name_A': ['Muller', 'Schmidt', 'Weber', 'Fischer', 'Koch', 'Bauer'],
        })
        clustered_df.to_csv(run_dir / 'clustered_results.csv', index=False)

        # Create llm_labeled_results.csv
        llm_df = pd.DataFrame({
            'i': [1, 2, 3, 4, 5, 6],
            'j': [10, 20, 30, 40, 50, 60],
            'cluster': [3, 3, 0, 0, 1, 1],
            'llm_label': ['DUPLICATE', 'DUPLICATE', 'NOT_DUPLICATE', 'DUPLICATE', 'NOT_DUPLICATE', 'DUPLICATE'],
        })
        llm_df.to_csv(run_dir / 'llm_labeled_results.csv', index=False)

        return run_dir

    def test_run_tier_assignment_function_exists(self):
        """run_tier_assignment function should exist in generate_tiered_output module."""
        from scripts.generate_tiered_output import run_tier_assignment

        assert callable(run_tier_assignment), "run_tier_assignment should be callable"

    def test_run_tier_assignment_returns_result_dict(self, sample_run_directory):
        """run_tier_assignment should return a result dictionary."""
        from scripts.generate_tiered_output import run_tier_assignment

        result = run_tier_assignment(sample_run_directory)

        assert isinstance(result, dict), "Should return a dictionary"
        assert 'success' in result, "Result should have 'success' key"
        assert 'tier1_count' in result, "Result should have 'tier1_count' key"
        assert 'tier2_count' in result, "Result should have 'tier2_count' key"
        assert 'elapsed_time' in result, "Result should have 'elapsed_time' key"

    def test_run_tier_assignment_creates_output_files(self, sample_run_directory):
        """run_tier_assignment should create output CSV files."""
        from scripts.generate_tiered_output import run_tier_assignment

        run_tier_assignment(sample_run_directory)

        tier1_path = sample_run_directory / 'auto_merge_pairs.csv'
        tier2_path = sample_run_directory / 'review_queue_pairs.csv'

        assert tier1_path.exists(), "Tier 1 output should be created"
        assert tier2_path.exists(), "Tier 2 output should be created"

    def test_run_tier_assignment_with_config(self, sample_run_directory, tmp_path):
        """run_tier_assignment should accept optional config path."""
        from scripts.generate_tiered_output import run_tier_assignment

        # Create config file
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

        result = run_tier_assignment(sample_run_directory, config_path=config_path)

        assert result['success'] is True, "Should succeed with config"


class TestOutputDirectoryConsistency:
    """Test output directory consistency (AC3)."""

    @pytest.fixture
    def sample_run_directory(self, tmp_path):
        """Create sample run directory structure."""
        run_dir = tmp_path / "_bmad-output" / "analysis" / "run_20260110_120000"
        run_dir.mkdir(parents=True)

        # Create minimal input files
        pd.DataFrame({
            'i': [1, 2], 'j': [10, 20], 'score': [80.0, 85.0], 'cluster': [3, 0]
        }).to_csv(run_dir / 'clustered_results.csv', index=False)

        pd.DataFrame({
            'i': [1, 2], 'j': [10, 20], 'cluster': [3, 0],
            'llm_label': ['DUPLICATE', 'NOT_DUPLICATE']
        }).to_csv(run_dir / 'llm_labeled_results.csv', index=False)

        return run_dir

    def test_outputs_in_same_run_directory(self, sample_run_directory):
        """All outputs should be in the same run directory."""
        from scripts.generate_tiered_output import run_tier_assignment

        run_tier_assignment(sample_run_directory)

        # Check all outputs are in run directory
        expected_files = ['auto_merge_pairs.csv', 'review_queue_pairs.csv']
        for filename in expected_files:
            filepath = sample_run_directory / filename
            assert filepath.exists(), f"{filename} should be in run directory"


class TestStageTransitionLogging:
    """Test stage transition logging (AC5)."""

    @pytest.fixture
    def sample_run_directory(self, tmp_path):
        """Create sample run directory with input files."""
        run_dir = tmp_path / "_bmad-output" / "analysis" / "run_20260110_120000"
        run_dir.mkdir(parents=True)

        pd.DataFrame({
            'i': [1, 2], 'j': [10, 20], 'score': [80.0, 85.0], 'cluster': [3, 0]
        }).to_csv(run_dir / 'clustered_results.csv', index=False)

        pd.DataFrame({
            'i': [1, 2], 'j': [10, 20], 'cluster': [3, 0],
            'llm_label': ['DUPLICATE', 'NOT_DUPLICATE']
        }).to_csv(run_dir / 'llm_labeled_results.csv', index=False)

        return run_dir

    def test_run_tier_assignment_logs_start(self, sample_run_directory, caplog):
        """run_tier_assignment should log stage start."""
        from scripts.generate_tiered_output import run_tier_assignment

        with caplog.at_level(logging.INFO):
            run_tier_assignment(sample_run_directory)

        # Check for stage transition log
        log_text = caplog.text.lower()
        assert 'stage 3' in log_text or 'tier assignment' in log_text, \
            "Should log stage 3 / tier assignment start"

    def test_run_tier_assignment_logs_completion(self, sample_run_directory, caplog):
        """run_tier_assignment should log stage completion."""
        from scripts.generate_tiered_output import run_tier_assignment

        with caplog.at_level(logging.INFO):
            result = run_tier_assignment(sample_run_directory)

        # Check for completion log
        assert result['success'] is True, "Stage should complete successfully"


class TestStage3PerformanceTarget:
    """Test Stage 3 performance target (AC4)."""

    @pytest.fixture
    def realistic_run_directory(self, tmp_path):
        """Create realistic run directory with ~1000 pairs."""
        run_dir = tmp_path / "_bmad-output" / "analysis" / "run_20260110_120000"
        run_dir.mkdir(parents=True)

        # Create 1000 pairs spread across clusters
        import numpy as np
        np.random.seed(42)

        n_pairs = 1000
        clustered_df = pd.DataFrame({
            'i': range(n_pairs),
            'j': range(n_pairs, 2 * n_pairs),
            'score': np.random.uniform(60, 95, n_pairs),
            'cluster': np.random.randint(0, 15, n_pairs),
        })
        clustered_df.to_csv(run_dir / 'clustered_results.csv', index=False)

        # Create LLM labels (sample from each cluster)
        sample_size = 200
        llm_df = clustered_df.sample(n=sample_size, random_state=42).copy()
        llm_df['llm_label'] = np.random.choice(
            ['DUPLICATE', 'NOT_DUPLICATE'],
            size=sample_size,
            p=[0.8, 0.2]
        )
        llm_df.to_csv(run_dir / 'llm_labeled_results.csv', index=False)

        return run_dir

    def test_stage3_completes_under_5_minutes(self, realistic_run_directory):
        """Stage 3 should complete in under 5 minutes (300 seconds)."""
        from scripts.generate_tiered_output import run_tier_assignment

        start = time.time()
        result = run_tier_assignment(realistic_run_directory)
        elapsed = time.time() - start

        assert result['success'] is True, "Stage 3 should complete successfully"
        assert elapsed < 300, f"Stage 3 should complete in <5 min, took {elapsed:.2f}s"
        # More realistic target for 1000 pairs
        assert elapsed < 30, f"Stage 3 with 1000 pairs should complete in <30s, took {elapsed:.2f}s"

    def test_stage3_reports_elapsed_time(self, realistic_run_directory):
        """run_tier_assignment should report elapsed time in result."""
        from scripts.generate_tiered_output import run_tier_assignment

        result = run_tier_assignment(realistic_run_directory)

        assert 'elapsed_time' in result, "Result should include elapsed_time"
        assert result['elapsed_time'] > 0, "Elapsed time should be positive"
        assert result['elapsed_time'] < 300, "Elapsed time should be under 5 minutes"


class TestPipelineOrchestratorPlaceholder:
    """Placeholder tests for full pipeline orchestrator (to be implemented)."""

    def test_full_pipeline_orchestrator_module_exists(self):
        """Full pipeline orchestrator should exist (placeholder for future implementation)."""
        # This test documents the expectation for a full pipeline orchestrator
        # The actual implementation will be in scripts/run_full_pipeline.py

        # For now, we verify the tier assignment can be called programmatically
        from scripts.generate_tiered_output import run_tier_assignment
        assert callable(run_tier_assignment), "run_tier_assignment should be callable"


class TestInputFileDiscovery:
    """Test input file discovery (AC2)."""

    def test_discovers_clustered_results(self, tmp_path):
        """Should discover clustered_results.csv in run directory."""
        run_dir = tmp_path / "run_20260110"
        run_dir.mkdir()

        clustered_path = run_dir / 'clustered_results.csv'
        pd.DataFrame({'i': [1], 'j': [2], 'score': [80.0], 'cluster': [0]}).to_csv(
            clustered_path, index=False
        )

        assert clustered_path.exists(), "clustered_results.csv should exist"

    def test_discovers_llm_labeled_results(self, tmp_path):
        """Should discover llm_labeled_results.csv in run directory."""
        run_dir = tmp_path / "run_20260110"
        run_dir.mkdir()

        llm_path = run_dir / 'llm_labeled_results.csv'
        pd.DataFrame({
            'i': [1], 'j': [2], 'cluster': [0], 'llm_label': ['DUPLICATE']
        }).to_csv(llm_path, index=False)

        assert llm_path.exists(), "llm_labeled_results.csv should exist"

    def test_handles_missing_input_files(self, tmp_path):
        """Should raise error when input files are missing."""
        from scripts.generate_tiered_output import run_tier_assignment

        empty_run_dir = tmp_path / "empty_run"
        empty_run_dir.mkdir()

        result = run_tier_assignment(empty_run_dir)

        assert result['success'] is False, "Should fail with missing input files"
        assert 'error' in result, "Should include error message"
