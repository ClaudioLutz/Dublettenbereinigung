"""
Test to verify address matching rules:
1. Street name can have small differences (fuzzy matching allowed)
2. Street number must be the same, BUT "10A" and "10" should match
3. Missing street number + some street number can also match
4. PLZ: no difference allowed (must be exact)
"""

import pandas as pd
from dedupe.preprocess import preprocess
from dedupe.scoring import score_pair


def test_rule1_street_name_fuzzy_matching():
    """Rule 1: Street name can have small differences"""
    
    df = pd.DataFrame([
        {
            "Vorname": "Hans",
            "Name": "Mueller",
            "Name2": "",
            "Strasse": "Hauptstrasse",  # Small typo
            "HausNummer": "10",
            "Plz": "8000",
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        },
        {
            "Vorname": "Hans",
            "Name": "Mueller",
            "Name2": "",
            "Strasse": "Hauptstr",  # Abbreviated version
            "HausNummer": "10",
            "Plz": "8000",
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        }
    ])
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols)
    
    assert result is not None, (
        "❌ FAILED: Street names 'Hauptstrasse' vs 'Hauptstr' should match (fuzzy matching)"
    )
    print(f"✅ Rule 1 PASS: Street name fuzzy matching works - Score: {result.score:.1f}%")
    return True


def test_rule2_street_number_10A_vs_10():
    """Rule 2: Street numbers "10A" and "10" should match (same base number)"""
    
    df = pd.DataFrame([
        {
            "Vorname": "Maria",
            "Name": "Schmidt",
            "Name2": "",
            "Strasse": "Bahnhofstrasse",
            "HausNummer": "10",  # No letter suffix
            "Plz": "8000",
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        },
        {
            "Vorname": "Maria",
            "Name": "Schmidt",
            "Name2": "",
            "Strasse": "Bahnhofstrasse",
            "HausNummer": "10A",  # With letter suffix
            "Plz": "8000",
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        }
    ])
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols)
    
    assert result is not None, (
        "❌ FAILED: Street numbers '10' and '10A' should match (same base number)"
    )
    print(f"✅ Rule 2 PASS: Street numbers '10' and '10A' match - Score: {result.score:.1f}%")
    return True


def test_rule2_different_street_numbers_reject():
    """Rule 2: Different street numbers (10 vs 20) should NOT match"""
    
    df = pd.DataFrame([
        {
            "Vorname": "Maria",
            "Name": "Schmidt",
            "Name2": "",
            "Strasse": "Bahnhofstrasse",
            "HausNummer": "10",  # Number 10
            "Plz": "8000",
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        },
        {
            "Vorname": "Maria",
            "Name": "Schmidt",
            "Name2": "",
            "Strasse": "Bahnhofstrasse",
            "HausNummer": "20",  # Number 20
            "Plz": "8000",
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        }
    ])
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols)
    
    assert result is None, (
        f"❌ FAILED: Different street numbers '10' vs '20' should NOT match, but got score: {result.score if result else 'None'}"
    )
    print(f"✅ Rule 2 PASS: Different street numbers '10' vs '20' correctly rejected")
    return True


def test_rule3_missing_street_number_can_match():
    """Rule 3: Missing street number + some street number can match"""
    
    df = pd.DataFrame([
        {
            "Vorname": "Peter",
            "Name": "Meier",
            "Name2": "",
            "Strasse": "Seestrasse",
            "HausNummer": "",  # No house number
            "Plz": "8000",
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        },
        {
            "Vorname": "Peter",
            "Name": "Meier",
            "Name2": "",
            "Strasse": "Seestrasse",
            "HausNummer": "42",  # Has house number
            "Plz": "8000",
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        }
    ])
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols)
    
    assert result is not None, (
        "❌ FAILED: Missing street number + filled street number should be allowed to match"
    )
    print(f"✅ Rule 3 PASS: Missing street number + filled street number match - Score: {result.score:.1f}%")
    return True


def test_rule4_plz_exact_match_required():
    """Rule 4: PLZ must be exact - no difference allowed"""
    
    df = pd.DataFrame([
        {
            "Vorname": "Anna",
            "Name": "Weber",
            "Name2": "",
            "Strasse": "Bahnhofstrasse",
            "HausNummer": "10",
            "Plz": "8000",  # Zurich
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        },
        {
            "Vorname": "Anna",
            "Name": "Weber",
            "Name2": "",
            "Strasse": "Bahnhofstrasse",
            "HausNummer": "10",
            "Plz": "8001",  # Different PLZ
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        }
    ])
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols)
    
    assert result is None, (
        f"❌ FAILED: Different PLZ (8000 vs 8001) should NOT match, but got score: {result.score if result else 'None'}"
    )
    print(f"✅ Rule 4 PASS: Different PLZ correctly rejected (8000 vs 8001)")
    return True


def test_rule4_plz_same_allows_match():
    """Rule 4: Same PLZ allows matching"""
    
    df = pd.DataFrame([
        {
            "Vorname": "Anna",
            "Name": "Weber",
            "Name2": "",
            "Strasse": "Bahnhofstrasse",
            "HausNummer": "10",
            "Plz": "8000",
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        },
        {
            "Vorname": "Anna",
            "Name": "Weber",
            "Name2": "",
            "Strasse": "Bahnhofstrasse",
            "HausNummer": "10",
            "Plz": "8000",  # Same PLZ
            "Ort": "Zurich",
            "Geburtstag": pd.NaT
        }
    ])
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols)
    
    assert result is not None, (
        "❌ FAILED: Same PLZ should allow matching"
    )
    assert result.score >= 90.0, (
        f"Expected high score for identical records, got {result.score}%"
    )
    print(f"✅ Rule 4 PASS: Same PLZ allows high confidence match - Score: {result.score:.1f}%")
    return True


def test_combined_rules():
    """Test all rules working together"""
    
    df = pd.DataFrame([
        {
            "Vorname": "Thomas",
            "Name": "Huber",
            "Name2": "",
            "Strasse": "Hauptstr",  # Abbreviated
            "HausNummer": "15",  # No suffix
            "Plz": "3000",
            "Ort": "Bern",
            "Geburtstag": pd.NaT
        },
        {
            "Vorname": "Thomas",
            "Name": "Huber",
            "Name2": "",
            "Strasse": "Hauptstrasse",  # Full name
            "HausNummer": "15B",  # With suffix
            "Plz": "3000",  # Same PLZ
            "Ort": "Bern",
            "Geburtstag": pd.NaT
        }
    ])
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols)
    
    assert result is not None, (
        "❌ FAILED: Combined rules - should match with fuzzy street + number suffix + same PLZ"
    )
    print(f"✅ Combined rules PASS: All rules work together - Score: {result.score:.1f}%")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("ADDRESS MATCHING RULES VERIFICATION TEST")
    print("=" * 70)
    print()
    
    all_passed = True
    
    try:
        print("Rule 1: Street name can have small differences (fuzzy matching)")
        test_rule1_street_name_fuzzy_matching()
        print()
    except AssertionError as e:
        print(str(e))
        all_passed = False
    
    try:
        print("Rule 2a: Street numbers '10' and '10A' should match")
        test_rule2_street_number_10A_vs_10()
        print()
    except AssertionError as e:
        print(str(e))
        all_passed = False
    
    try:
        print("Rule 2b: Different street numbers should NOT match")
        test_rule2_different_street_numbers_reject()
        print()
    except AssertionError as e:
        print(str(e))
        all_passed = False
    
    try:
        print("Rule 3: Missing street number + filled street number can match")
        test_rule3_missing_street_number_can_match()
        print()
    except AssertionError as e:
        print(str(e))
        all_passed = False
    
    try:
        print("Rule 4a: Different PLZ should NOT match")
        test_rule4_plz_exact_match_required()
        print()
    except AssertionError as e:
        print(str(e))
        all_passed = False
    
    try:
        print("Rule 4b: Same PLZ allows matching")
        test_rule4_plz_same_allows_match()
        print()
    except AssertionError as e:
        print(str(e))
        all_passed = False
    
    try:
        print("Combined: All rules working together")
        test_combined_rules()
        print()
    except AssertionError as e:
        print(str(e))
        all_passed = False
    
    print("=" * 70)
    if all_passed:
        print("🎉 ALL RULES VERIFIED SUCCESSFULLY!")
        print("=" * 70)
        print()
        print("Summary:")
        print("  ✅ Rule 1: Street name fuzzy matching works")
        print("  ✅ Rule 2: Street numbers match correctly (10 = 10A, but 10 ≠ 20)")
        print("  ✅ Rule 3: Missing street numbers allowed")
        print("  ✅ Rule 4: PLZ exact matching enforced")
    else:
        print("❌ SOME RULES FAILED - See details above")
        print("=" * 70)
        exit(1)
