"""
Test first-word token matching bonus functionality
"""
import pandas as pd
import pytest
from dedupe.scoring import score_pair, get_first_word_bonus


def test_first_word_bonus_calculation():
    """Test that first-word bonus is calculated correctly"""
    
    # Test case 1: First words match, everything else matches perfectly
    bonus = get_first_word_bonus(
        first_a="joao manuel",
        first_b="joao",
        plz_i="900000",
        plz_j="900000",
        house_num_i="25",
        house_num_j="25",
        street_i="zwyssigstrasse",
        street_j="zwyssigstrasse",
        ort_i="st. gallen",
        ort_j="st. gallen"
    )
    assert bonus == 0.10, f"Expected 10% bonus when everything matches, got {bonus}"
    
    # Test case 2: First words match, but address is imperfect
    bonus = get_first_word_bonus(
        first_a="joao manuel",
        first_b="joao",
        plz_i="900000",
        plz_j="900000",
        house_num_i="25",
        house_num_j="26",  # Different house number
        street_i="zwyssigstrasse",
        street_j="zwyssigstrasse",
        ort_i="st. gallen",
        ort_j="st. gallen"
    )
    assert bonus == 0.05, f"Expected 5% bonus when address imperfect, got {bonus}"
    
    # Test case 3: First words don't match
    bonus = get_first_word_bonus(
        first_a="joao manuel",
        first_b="pedro",
        plz_i="900000",
        plz_j="900000",
        house_num_i="25",
        house_num_j="25",
        street_i="zwyssigstrasse",
        street_j="zwyssigstrasse",
        ort_i="st. gallen",
        ort_j="st. gallen"
    )
    assert bonus == 0.0, f"Expected 0% bonus when first words don't match, got {bonus}"
    
    # Test case 4: One name has only one word
    bonus = get_first_word_bonus(
        first_a="joao",
        first_b="joao",
        plz_i="900000",
        plz_j="900000",
        house_num_i="25",
        house_num_j="25",
        street_i="zwyssigstrasse",
        street_j="zwyssigstrasse",
        ort_i="st. gallen",
        ort_j="st. gallen"
    )
    assert bonus == 0.10, f"Expected 10% bonus when both single-word names match, got {bonus}"


def test_first_word_bonus_integration():
    """Test that first-word bonus helps borderline cases cross the threshold"""
    
    # Create test data: "Joao Manuel" vs "Joao" with same last name and address
    # This should score ~74% without bonus, but ~79-84% with bonus
    data = pd.DataFrame({
        'vorname': ['joao manuel', 'joao'],
        'name': ['pulquerio calado', 'pulquerio calado'],
        'name2': ['', ''],
        'strasse': ['zwyssigstrasse', 'zwyssigstrasse'],
        'hausnummer': ['25', '25'],
        'plz': ['900000', '900000'],
        'ort': ['st. gallen', 'st. gallen'],
        'geburtstag': [pd.NaT, pd.NaT],
        'jahrgang': [-1, -1]
    })
    
    # Preprocess columns (simplified for test)
    cols = {
        'first': data['vorname'],
        'last': data['name'],
        'name2': data['name2'],
        'street': data['strasse'],
        'house': data['hausnummer'],
        'house_num': data['hausnummer'],  # Simplified
        'house_sfx': pd.Series(['', ''], dtype=str),
        'plz': data['plz'],
        'ort': data['ort'],
        'dob_ymd': pd.Series([-1, -1], dtype=int),
        'yob': pd.Series([-1, -1], dtype=int)
    }
    
    # Score the pair
    result = score_pair(i=0, j=1, cols=cols, fuzzy_threshold=0.80)
    
    # Should return a match (not None) due to first-word bonus
    assert result is not None, "Expected match with first-word bonus, got None"
    
    # Confidence should be boosted (around 80-85%)
    assert result.score >= 75.0, f"Expected score >= 75% with bonus, got {result.score:.2f}%"
    assert result.reason in ['fuzzy_normal', 'fuzzy_swapped'], f"Unexpected reason: {result.reason}"


def test_name_similarity_gates_reject_family_members():
    """Test that stricter gates (75% first, 80% last) reject family members"""
    
    # Test case 1: Hermann vs Andreas Bösch (different first names, same last name, same address)
    data = pd.DataFrame({
        'vorname': ['hermann', 'andreas'],
        'name': ['bösch', 'bösch'],
        'name2': ['', ''],
        'strasse': ['zwyssigstrasse', 'zwyssigstrasse'],
        'hausnummer': ['24', '24'],
        'plz': ['900000', '900000'],
        'ort': ['st. gallen', 'st. gallen'],
        'geburtstag': [pd.Timestamp('1943-04-03'), pd.NaT],
        'jahrgang': [1943, -1]
    })
    
    cols = {
        'first': data['vorname'],
        'last': data['name'],
        'name2': data['name2'],
        'street': data['strasse'],
        'house': data['hausnummer'],
        'house_num': data['hausnummer'],
        'house_sfx': pd.Series(['', ''], dtype=str),
        'plz': data['plz'],
        'ort': data['ort'],
        'dob_ymd': pd.Series([-1, -1], dtype=int),
        'yob': pd.Series([1943, -1], dtype=int)
    }
    
    # Should NOT match (first name similarity ~40%, below 75% threshold)
    result = score_pair(i=0, j=1, cols=cols, fuzzy_threshold=0.80)
    assert result is None, f"Expected no match for Hermann vs Andreas, got {result}"
    
    # Test case 2: Ueli Meier vs Jacqueline Bacher (different surnames)
    data = pd.DataFrame({
        'vorname': ['ueli', 'jacqueline'],
        'name': ['meier', 'bacher'],
        'name2': ['', ''],
        'strasse': ['zwyssigstrasse', 'zwyssigstrasse'],
        'hausnummer': ['35', '35'],
        'plz': ['900000', '900000'],
        'ort': ['st. gallen', 'st. gallen'],
        'geburtstag': [pd.Timestamp('1965-07-01'), pd.NaT],
        'jahrgang': [1965, -1]
    })
    
    cols = {
        'first': data['vorname'],
        'last': data['name'],
        'name2': data['name2'],
        'street': data['strasse'],
        'house': data['hausnummer'],
        'house_num': data['hausnummer'],
        'house_sfx': pd.Series(['', ''], dtype=str),
        'plz': data['plz'],
        'ort': data['ort'],
        'dob_ymd': pd.Series([-1, -1], dtype=int),
        'yob': pd.Series([1965, -1], dtype=int)
    }
    
    # Should NOT match (last name similarity ~20%, below 80% threshold)
    result = score_pair(i=0, j=1, cols=cols, fuzzy_threshold=0.80)
    assert result is None, f"Expected no match for Meier vs Bacher, got {result}"


if __name__ == '__main__':
    test_first_word_bonus_calculation()
    print("✓ First-word bonus calculation tests passed")
    
    test_first_word_bonus_integration()
    print("✓ First-word bonus integration test passed")
    
    test_name_similarity_gates_reject_family_members()
    print("✓ Name similarity gates test passed")
    
    print("\n✅ All tests passed!")
