"""
Test suite for dedupe/ module business rules alignment with duplicate_checker_optimized.py
"""

import pandas as pd
import numpy as np
from dedupe.preprocess import preprocess
from dedupe.scoring import score_pair, check_zweitname, compare_names_with_swap


def test_german_umlaut_normalization():
    """Test that German umlauts are normalized correctly"""
    print("Testing German Umlaut Normalization...")
    
    df = pd.DataFrame({
        'Vorname': ['Max', 'Max'],
        'Name': ['Müller', 'Mueller'],
        'Name2': ['', ''],
        'Strasse': ['Hauptstr', 'Hauptstr'],
        'Plz': ['8000', '8000'],
        'HausNummer': ['1', '1'],
        'Ort': ['Zurich', 'Zurich'],
        'Geburtstag': ['1980-01-01', '1980-01-01']
    })
    
    cols = preprocess(df)
    
    # Both should normalize to 'mueller'
    assert cols['last'].iloc[0] == cols['last'].iloc[1], \
        f"Expected equal: {cols['last'].iloc[0]} == {cols['last'].iloc[1]}"
    
    result = score_pair(0, 1, cols)
    assert result is not None, "Should match"
    assert result.reason == 'exact_normal', f"Expected exact_normal, got {result.reason}"
    assert result.score >= 90, f"Expected score >= 90, got {result.score}"
    
    print("✅ German Umlaut Normalization: PASS")
    return True


def test_name2_rule_both_populated():
    """Test Name2 rule when both fields are populated"""
    print("Testing Name2 Rule - Both Populated...")
    
    # Should match
    assert check_zweitname('maria', 'schmidt', 'maria', 'schmidt') == True
    
    # Should not match
    assert check_zweitname('maria', 'schmidt', 'anna', 'schmidt') == False
    
    print("✅ Name2 Rule - Both Populated: PASS")
    return True


def test_name2_rule_compound_surname():
    """Test Name2 rule for compound surnames"""
    print("Testing Name2 Rule - Compound Surname...")
    
    # One has compound surname, other has it split
    assert check_zweitname('', 'rohner-stassek', '-stassek', 'rohner') == True
    assert check_zweitname('-stassek', 'rohner', '', 'rohner-stassek') == True
    
    # Should not match if suffix doesn't match
    assert check_zweitname('', 'schmidt', '-hansen', 'mueller') == False
    
    print("✅ Name2 Rule - Compound Surname: PASS")
    return True


def test_name_swapping_detection():
    """Test that name swapping is detected and scores 100 when everything matches"""
    print("Testing Name Swapping Detection...")
    
    df = pd.DataFrame({
        'Vorname': ['Anna', 'Schmidt'],
        'Name': ['Schmidt', 'Anna'],
        'Name2': ['', ''],
        'Strasse': ['Hauptstr', 'Hauptstr'],
        'Plz': ['8000', '8000'],
        'HausNummer': ['1', '1'],
        'Ort': ['Zurich', 'Zurich'],
        'Geburtstag': ['1980-01-01', '1980-01-01']
    })
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols)
    
    assert result is not None, "Should match"
    assert result.is_swapped == True, f"Expected is_swapped=True, got {result.is_swapped}"
    assert result.reason == 'exact_swapped', f"Expected exact_swapped, got {result.reason}"
    # NEW: Score should be 100 when everything else matches perfectly
    assert result.score == 100.0, f"Expected score 100.0, got {result.score}"
    
    print("✅ Name Swapping Detection: PASS")
    return True


def test_name_swapping_with_name2_in_first():
    """Test that swapped names with Name2 in Vorname field are detected and score 100"""
    print("Testing Name Swapping with Name2 in Vorname...")
    
    df = pd.DataFrame({
        'Vorname': ['Hans', 'Müller-Bensel'],
        'Name': ['Müller', 'Hans'],
        'Name2': ['-Bensel', ''],
        'Strasse': ['Hauptstrasse', 'Hauptstrasse'],
        'Plz': ['8000', '8000'],
        'HausNummer': ['10', '10A'],
        'Ort': ['Zürich', 'Zürich'],
        'Geburtstag': ['1980-01-01', '1980-01-01'],
    })
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols)
    
    assert result is not None, f"Should match, but got None"
    assert result.reason == 'exact_swapped', f"Expected exact_swapped, got {result.reason}"
    assert result.is_swapped is True, f"Expected is_swapped=True, got {result.is_swapped}"
    # NEW: Score should be 100 when everything else matches perfectly (10 vs 10A is equivalent)
    assert result.score == 100.0, f"Expected score 100.0, got {result.score}"
    
    print("✅ Name Swapping with Name2 in Vorname: PASS")
    return True


def test_exact_vs_fuzzy_stages():
    """Test two-stage architecture (exact vs fuzzy)"""
    print("Testing Two-Stage Architecture...")
    
    # Stage 1: Exact match
    df_exact = pd.DataFrame({
        'Vorname': ['Max', 'Max'],
        'Name': ['Müller', 'Mueller'],  # Should be exact after normalization
        'Name2': ['', ''],
        'Strasse': ['Hauptstr', 'Hauptstr'],
        'Plz': ['8000', '8000'],
        'HausNummer': ['1', '1'],
        'Geburtstag': ['1980-01-01', '1980-01-01']
    })
    
    cols_exact = preprocess(df_exact)
    result_exact = score_pair(0, 1, cols_exact)
    
    assert result_exact is not None, "Exact should match"
    assert result_exact.reason == 'exact_normal', f"Expected exact_normal, got {result_exact.reason}"
    assert result_exact.score >= 90, f"Expected score >= 90, got {result_exact.score}"
    
    # Stage 2: Fuzzy match
    df_fuzzy = pd.DataFrame({
        'Vorname': ['Max', 'Mux'],  # Typo
        'Name': ['Mueller', 'Mueller'],
        'Name2': ['', ''],
        'Strasse': ['Hauptstr', 'Hauptstr'],
        'Plz': ['8000', '8000'],
        'HausNummer': ['1', '1'],
        'Geburtstag': ['1980-01-01', '1980-01-01']
    })
    
    cols_fuzzy = preprocess(df_fuzzy)
    result_fuzzy = score_pair(0, 1, cols_fuzzy)
    
    assert result_fuzzy is not None, "Fuzzy should match"
    assert result_fuzzy.reason == 'fuzzy_normal', f"Expected fuzzy_normal, got {result_fuzzy.reason}"
    assert result_fuzzy.score < result_exact.score, \
        f"Fuzzy score ({result_fuzzy.score}) should be < exact score ({result_exact.score})"
    
    print("✅ Two-Stage Architecture: PASS")
    return True


def test_date_rule():
    """Test that date rule rejects mismatched years"""
    print("Testing Date Rule...")
    
    df = pd.DataFrame({
        'Vorname': ['Max', 'Max'],
        'Name': ['Mueller', 'Mueller'],
        'Name2': ['', ''],
        'Strasse': ['', ''],
        'Plz': ['', ''],
        'HausNummer': ['', ''],
        'Geburtstag': ['1980-01-01', '1985-01-01']  # Different years
    })
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols)
    
    assert result is None, f"Should not match (different years), but got: {result}"
    
    print("✅ Date Rule: PASS")
    return True


def test_compare_names_with_swap():
    """Test the compare_names_with_swap function"""
    print("Testing compare_names_with_swap function...")
    
    # Normal match
    result_normal = compare_names_with_swap('max', 'mueller', 'max', 'mueller')
    assert result_normal['is_swapped'] == False
    assert result_normal['best_score'] > 0.9
    
    # Swapped match
    result_swapped = compare_names_with_swap('anna', 'schmidt', 'schmidt', 'anna')
    assert result_swapped['is_swapped'] == True
    assert result_swapped['best_score'] > 0.9
    
    print("✅ compare_names_with_swap function: PASS")
    return True


def run_all_tests():
    """Run all business rules tests"""
    print("\n" + "="*60)
    print("DEDUPE BUSINESS RULES ALIGNMENT TEST SUITE")
    print("="*60 + "\n")
    
    tests = [
        test_german_umlaut_normalization,
        test_name2_rule_both_populated,
        test_name2_rule_compound_surname,
        test_name_swapping_detection,
        test_name_swapping_with_name2_in_first,
        test_exact_vs_fuzzy_stages,
        test_date_rule,
        test_compare_names_with_swap,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__}: FAILED - {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: ERROR - {e}")
            failed += 1
        print()
    
    print("="*60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*60)
    
    if failed == 0:
        print("\n✅ ALL TESTS PASSED - Business rules aligned with duplicate_checker_optimized.py")
    else:
        print(f"\n⚠️ {failed} test(s) failed - Please review implementation")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
