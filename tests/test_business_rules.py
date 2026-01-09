"""
Regression tests for business rules using ground truth validated pairs.

These tests ensure that scoring logic remains consistent with manually validated
entity pairs. Tests will fail if rule changes break previously validated behavior.
"""

import pytest
import pandas as pd
import os
from pathlib import Path

# Import scoring function (adjust path as needed)
# from dedupe.scoring import score_pair


# Ground truth file paths
GROUND_TRUTH_DIR = Path("ground_truth")
CLEAR_DUPLICATES = GROUND_TRUTH_DIR / "clear_duplicates.csv"
CLEAR_NON_DUPLICATES = GROUND_TRUTH_DIR / "clear_non_duplicates.csv"
EDGE_CASES = GROUND_TRUTH_DIR / "edge_cases.csv"
BOUNDARY_CASES = GROUND_TRUTH_DIR / "boundary_cases.csv"


def load_ground_truth_pairs(filepath: Path):
    """Load ground truth pairs if file exists."""
    if not filepath.exists():
        pytest.skip(f"Ground truth file not found: {filepath}")

    df = pd.read_csv(filepath)
    if len(df) == 0:
        pytest.skip(f"Ground truth file is empty: {filepath}")

    # Convert to list of dicts for parametrization
    return df.to_dict('records')


# Parametrized tests for clear duplicates
@pytest.mark.parametrize(
    "pair",
    load_ground_truth_pairs(CLEAR_DUPLICATES),
    ids=lambda x: f"pair_{x.get('i', '?')}_{x.get('j', '?')}"
)
def test_clear_duplicates(pair):
    """
    Test that pairs in clear_duplicates.csv score >= 95% (high confidence).

    These are manually validated true matches that the system should
    consistently identify with high confidence.
    """
    # TODO: Implement when score_pair function is available
    # result = score_pair(pair['i'], pair['j'], cols)
    # assert result is not None, f"Pair should not be rejected by gates"
    # assert result.score >= 95, f"Clear duplicate should score >=95%, got {result.score:.1f}%"

    # Placeholder for now
    pytest.skip("Regression test framework ready - requires score_pair integration")


# Parametrized tests for clear non-duplicates
@pytest.mark.parametrize(
    "pair",
    load_ground_truth_pairs(CLEAR_NON_DUPLICATES),
    ids=lambda x: f"pair_{x.get('i', '?')}_{x.get('j', '?')}"
)
def test_clear_non_duplicates(pair):
    """
    Test that pairs in clear_non_duplicates.csv score < 75% or are rejected.

    These are manually validated non-matches that the system should
    consistently reject or score with low confidence.
    """
    # TODO: Implement when score_pair function is available
    # result = score_pair(pair['i'], pair['j'], cols)
    # if result is None:
    #     pass  # Correctly rejected by gates
    # else:
    #     assert result.score < 75, f"Clear non-duplicate should score <75%, got {result.score:.1f}%"

    # Placeholder for now
    pytest.skip("Regression test framework ready - requires score_pair integration")


# Parametrized tests for edge cases
@pytest.mark.parametrize(
    "pair",
    load_ground_truth_pairs(EDGE_CASES),
    ids=lambda x: f"pair_{x.get('i', '?')}_{x.get('j', '?')}"
)
def test_edge_cases(pair):
    """
    Test that pairs in edge_cases.csv remain in review queue (65-95% range).

    These are borderline cases that require human review. The system should
    not make high-confidence decisions about these pairs.
    """
    # TODO: Implement when score_pair function is available
    # result = score_pair(pair['i'], pair['j'], cols)
    # if result is not None:
    #     assert 65 <= result.score <= 95, f"Edge case should score 65-95%, got {result.score:.1f}%"

    # Placeholder for now
    pytest.skip("Regression test framework ready - requires score_pair integration")


# Parametrized tests for boundary cases
@pytest.mark.parametrize(
    "pair",
    load_ground_truth_pairs(BOUNDARY_CASES),
    ids=lambda x: f"pair_{x.get('i', '?')}_{x.get('j', '?')}"
)
def test_boundary_cases(pair):
    """
    Test that pairs in boundary_cases.csv score near threshold (70-80% range).

    These are at-threshold cases where small rule changes might shift
    classification. Tests ensure deliberate threshold behavior.
    """
    # TODO: Implement when score_pair function is available
    # result = score_pair(pair['i'], pair['j'], cols)
    # if result is not None:
    #     # Within ±5 points of 75% threshold
    #     assert 70 <= result.score <= 80, f"Boundary case should score 70-80%, got {result.score:.1f}%"

    # Placeholder for now
    pytest.skip("Regression test framework ready - requires score_pair integration")


# Helper test to verify ground truth file structure
def test_ground_truth_structure():
    """Verify ground truth files have required columns if they exist."""
    required_columns = ['i', 'j', 'score', 'manual_label']

    for filepath in [CLEAR_DUPLICATES, CLEAR_NON_DUPLICATES, EDGE_CASES, BOUNDARY_CASES]:
        if filepath.exists():
            df = pd.read_csv(filepath)
            for col in required_columns:
                assert col in df.columns, f"{filepath.name} missing required column: {col}"
