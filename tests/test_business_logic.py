"""
Tests for Business Logic and Duplicate Checker
==============================================
"""

import pytest
import pandas as pd
from dublettenbereinigung.duplicate_checker_optimized import UltraFastDuplicateChecker, FastBusinessRules, OptimizedFuzzyMatcher

@pytest.fixture
def comprehensive_test_data() -> pd.DataFrame:
    """Create comprehensive test data covering all scenarios"""
    test_cases = [
        # Test 1 & 2: Exact normal match (should be 90-100% confidence, exact_normal)
        {
            'Name': 'Mustermann',
            'Vorname': 'Max',
            'Name2': '',
            'Strasse': 'Musterstrasse',
            'HausNummer': '1',
            'Plz': '12345',
            'Ort': 'Musterstadt',
            'Geburtstag': '1980-01-15',
            'Jahrgang': None,
            'TestCase': 'exact_normal_A'
        },
        {
            'Name': 'Mustermann',
            'Vorname': 'Max',
            'Name2': '',
            'Strasse': 'Musterstrasse',
            'HausNummer': '1',
            'Plz': '12345',
            'Ort': 'Musterstadt',
            'Geburtstag': '1980-01-15',
            'Jahrgang': None,
            'TestCase': 'exact_normal_B'
        },
        
        # Test 3 & 4: Exact swapped match (should be 85-95% confidence, exact_swapped)
        {
            'Name': 'Schmidt',
            'Vorname': 'Anna',
            'Name2': '',
            'Strasse': 'Schmidtweg',
            'HausNummer': '10',
            'Plz': '54321',
            'Ort': 'Schmidtstadt',
            'Geburtstag': '1975-05-20',
            'Jahrgang': None,
            'TestCase': 'exact_swapped_A'
        },
        {
            'Name': 'Anna',  # Swapped!
            'Vorname': 'Schmidt',  # Swapped!
            'Name2': '',
            'Strasse': 'Schmidtweg',
            'HausNummer': '10',
            'Plz': '54321',
            'Ort': 'Schmidtstadt',
            'Geburtstag': '1975-05-20',
            'Jahrgang': None,
            'TestCase': 'exact_swapped_B'
        },
        
        # Test 5 & 6: Fuzzy normal match with typo (should be 70-90% confidence, fuzzy_normal)
        {
            'Name': 'Mueller',
            'Vorname': 'Hans',
            'Name2': '',
            'Strasse': 'Muellerweg',
            'HausNummer': '5',
            'Plz': '11111',
            'Ort': 'Muellerstadt',
            'Geburtstag': '1985-03-10',
            'Jahrgang': None,
            'TestCase': 'fuzzy_normal_A'
        },
        {
            'Name': 'Mueller',
            'Vorname': 'Haus',  # Typo: Hans -> Haus (80% similar)
            'Name2': '',
            'Strasse': 'Muellerweg',
            'HausNummer': '5',
            'Plz': '11111',
            'Ort': 'Muellerstadt',
            'Geburtstag': '1985-03-10',
            'Jahrgang': None,
            'TestCase': 'fuzzy_normal_B'
        },
        
        # Test 7 & 8: Fuzzy swapped match (should be 65-85% confidence, fuzzy_swapped)
        {
            'Name': 'Weber',
            'Vorname': 'Thomas',
            'Name2': '',
            'Strasse': 'Weberplatz',
            'HausNummer': '7',
            'Plz': '22222',
            'Ort': 'Weberstadt',
            'Geburtstag': '1990-12-01',
            'Jahrgang': None,
            'TestCase': 'fuzzy_swapped_A'
        },
        {
            'Name': 'Tomas',  # Swapped + typo: Thomas -> Tomas
            'Vorname': 'Weber',  # Swapped + typo: Weber -> Weber (90% similar)
            'Name2': '',
            'Strasse': 'Weberplatz',
            'HausNummer': '7',
            'Plz': '22222',
            'Ort': 'Weberstadt',
            'Geburtstag': '1990-12-01',
            'Jahrgang': None,
            'TestCase': 'fuzzy_swapped_B'
        },
        
        # Test 9 & 10: German umlaut normalization (should match as exact_normal)
        {
            'Name': 'Müller',
            'Vorname': 'Karl',
            'Name2': '',
            'Strasse': 'Müllerstrasse',
            'HausNummer': '3',
            'Plz': '33333',
            'Ort': 'Müllendorf',
            'Geburtstag': '1978-08-15',
            'Jahrgang': None,
            'TestCase': 'umlaut_A'
        },
        {
            'Name': 'Mueller',  # Normalized version
            'Vorname': 'Karl',
            'Name2': '',
            'Strasse': 'Müllerstrasse',
            'HausNummer': '3',
            'Plz': '33333',
            'Ort': 'Müllendorf',
            'Geburtstag': '1978-08-15',
            'Jahrgang': None,
            'TestCase': 'umlaut_B'
        },
        
        # Test 11 & 12: Zweitname rule violation (should NOT match)
        {
            'Name': 'Wagner',
            'Vorname': 'Peter',
            'Name2': 'Franz',
            'Strasse': 'Wagnerweg',
            'HausNummer': '12',
            'Plz': '44444',
            'Ort': 'Wagnerstadt',
            'Geburtstag': '1982-04-20',
            'Jahrgang': None,
            'TestCase': 'zweitname_violation_A'
        },
        {
            'Name': 'Wagner',
            'Vorname': 'Peter',
            'Name2': 'Josef',  # Different Zweitname!
            'Strasse': 'Wagnerweg',
            'HausNummer': '12',
            'Plz': '44444',
            'Ort': 'Wagnerstadt',
            'Geburtstag': '1982-04-20',
            'Jahrgang': None,
            'TestCase': 'zweitname_violation_B'
        },
        
        # Test 13 & 14: Zweitname rule passes (case insensitive)
        {
            'Name': 'Fischer',
            'Vorname': 'Maria',
            'Name2': 'Anna',
            'Strasse': 'Fischerplatz',
            'HausNummer': '8',
            'Plz': '55555',
            'Ort': 'Fischerstadt',
            'Geburtstag': '1988-06-30',
            'Jahrgang': None,
            'TestCase': 'zweitname_pass_A'
        },
        {
            'Name': 'Fischer',
            'Vorname': 'Maria',
            'Name2': 'anna',  # Case insensitive match
            'Strasse': 'Fischerplatz',
            'HausNummer': '8',
            'Plz': '55555',
            'Ort': 'Fischerstadt',
            'Geburtstag': '1988-06-30',
            'Jahrgang': None,
            'TestCase': 'zweitname_pass_B'
        },
        
        # Test 15 & 16: Date rule - Geburtstag vs Jahrgang (should match)
        {
            'Name': 'Koch',
            'Vorname': 'Lukas',
            'Name2': '',
            'Strasse': 'Kochweg',
            'HausNummer': '15',
            'Plz': '66666',
            'Ort': 'Kochstadt',
            'Geburtstag': '1992-11-25',  # Year 1992
            'Jahrgang': None,
            'TestCase': 'date_geburtstag_A'
        },
        {
            'Name': 'Koch',
            'Vorname': 'Lukas',
            'Name2': '',
            'Strasse': 'Kochweg',
            'HausNummer': '15',
            'Plz': '66666',
            'Ort': 'Kochstadt',
            'Geburtstag': None,
            'Jahrgang': '1992',  # Should match birth year
            'TestCase': 'date_jahrgang_B'
        },
        
        # Test 17 & 18: Date rule violation (should NOT match)
        {
            'Name': 'Becker',
            'Vorname': 'Sophie',
            'Name2': '',
            'Strasse': 'Beckerstrasse',
            'HausNummer': '20',
            'Plz': '77777',
            'Ort': 'Beckerstadt',
            'Geburtstag': '1995-03-14',
            'Jahrgang': None,
            'TestCase': 'date_violation_A'
        },
        {
            'Name': 'Becker',
            'Vorname': 'Sophie',
            'Name2': '',
            'Strasse': 'Beckerstrasse',
            'HausNummer': '20',
            'Plz': '77777',
            'Ort': 'Beckerstadt',
            'Geburtstag': None,
            'Jahrgang': '1998',  # Different year!
            'TestCase': 'date_violation_B'
        },
        
        # Test 19 & 20: Rule 4 test - Geburtstag takes precedence over Jahrgang
        {
            'Name': 'Hoffmann',
            'Vorname': 'Julia',
            'Name2': '',
            'Strasse': 'Hoffmannweg',
            'HausNummer': '25',
            'Plz': '88888',
            'Ort': 'Hoffmannstadt',
            'Geburtstag': '1987-07-18',  # Year 1987
            'Jahrgang': '1980',  # Should be ignored
            'TestCase': 'rule4_A'
        },
        {
            'Name': 'Hoffmann',
            'Vorname': 'Julia',
            'Name2': '',
            'Strasse': 'Hoffmannweg',
            'HausNummer': '25',
            'Plz': '88888',
            'Ort': 'Hoffmannstadt',
            'Geburtstag': None,
            'Jahrgang': '1987',  # Should match birth year
            'TestCase': 'rule4_B'
        },
        
        # Test 21 & 22: Compound surname - name2 as suffix of name (should match)
        {
            'Name': 'Rohner-Stassek',
            'Vorname': 'Ruth',
            'Name2': '',
            'Strasse': 'Ringstrasse',
            'HausNummer': '42',
            'Plz': '964200',
            'Ort': 'Ebnat-Kappel',
            'Geburtstag': '28.07.1955',
            'Jahrgang': '1955',
            'TestCase': 'compound_surname_A'
        },
        {
            'Name': 'Rohner',
            'Vorname': 'Ruth',
            'Name2': '-Stassek',  # Matches end of "Rohner-Stassek"
            'Strasse': 'Ringstrasse',
            'HausNummer': '42',
            'Plz': '964200',
            'Ort': 'Ebnat-Kappel',
            'Geburtstag': '28.07.1955',
            'Jahrgang': '1955',
            'TestCase': 'compound_surname_B'
        },
        
        # Test 23 & 24: Phonetic match - Meyer/Maier (should match via phonetic)
        {
            'Name': 'Meyer',
            'Vorname': 'Hans',
            'Name2': '',
            'Strasse': 'Bahnhofstrasse',
            'HausNummer': '10',
            'Plz': '8001',
            'Ort': 'Zürich',
            'Geburtstag': '1980-01-01',
            'Jahrgang': '',
            'TestCase': 'phonetic_meyer_A'
        },
        {
            'Name': 'Maier',
            'Vorname': 'Hans',
            'Name2': '',
            'Strasse': 'Bahnhofstrasse',
            'HausNummer': '10',
            'Plz': '8001',
            'Ort': 'Zürich',
            'Geburtstag': '1980-01-01',
            'Jahrgang': '',
            'TestCase': 'phonetic_maier_B'
        },
        
        # Test 25 & 26: Phonetic match - Schmidt/Schmitt (should match via phonetic)
        {
            'Name': 'Schmidt',
            'Vorname': 'Anna',
            'Name2': '',
            'Strasse': 'Hauptstrasse',
            'HausNummer': '5',
            'Plz': '3000',
            'Ort': 'Bern',
            'Geburtstag': '1975-05-15',
            'Jahrgang': '',
            'TestCase': 'phonetic_schmidt_A'
        },
        {
            'Name': 'Schmitt',
            'Vorname': 'Anna',
            'Name2': '',
            'Strasse': 'Hauptstrasse',
            'HausNummer': '5',
            'Plz': '3000',
            'Ort': 'Bern',
            'Geburtstag': '1975-05-15',
            'Jahrgang': '',
            'TestCase': 'phonetic_schmitt_B'
        },
        
        # Test 27 & 28: NO phonetic match - Müller/Miler (different phonetic codes)
        {
            'Name': 'Müller',
            'Vorname': 'Peter',
            'Name2': '',
            'Strasse': 'Dorfstrasse',
            'HausNummer': '1',
            'Plz': '4000',
            'Ort': 'Basel',
            'Geburtstag': '1990-01-01',
            'Jahrgang': '',
            'TestCase': 'no_phonetic_muller_A'
        },
        {
            'Name': 'Miler',  # Different phonetic code
            'Vorname': 'Peter',
            'Name2': '',
            'Strasse': 'Dorfstrasse',
            'HausNummer': '1',
            'Plz': '4000',
            'Ort': 'Basel',
            'Geburtstag': '1990-01-01',
            'Jahrgang': '',
            'TestCase': 'no_phonetic_miler_B'
        },
        
        # Test 29 & 30: Phonetic with name swap - Wagner/Vagner
        {
            'Name': 'Wagner',
            'Vorname': 'Klaus',
            'Name2': '',
            'Strasse': 'Seestrasse',
            'HausNummer': '20',
            'Plz': '6000',
            'Ort': 'Luzern',
            'Geburtstag': '1985-03-10',
            'Jahrgang': '',
            'TestCase': 'phonetic_swapped_wagner_A'
        },
        {
            'Name': 'Klaus',  # Swapped
            'Vorname': 'Vagner',  # Phonetically matches Wagner
            'Name2': '',
            'Strasse': 'Seestrasse',
            'HausNummer': '20',
            'Plz': '6000',
            'Ort': 'Luzern',
            'Geburtstag': '1985-03-10',
            'Jahrgang': '',
            'TestCase': 'phonetic_swapped_vagner_B'
        },
        
        # Test 31: No match case (completely different record)
        {
            'Name': 'Different',
            'Vorname': 'Person',
            'Name2': '',
            'Strasse': 'Other Street',
            'HausNummer': '99',
            'Plz': '99999',
            'Ort': 'Other City',
            'Geburtstag': '2000-01-01',
            'Jahrgang': None,
            'TestCase': 'no_match'
        },
    ]
    return pd.DataFrame(test_cases)

def test_duplicate_analysis(comprehensive_test_data):
    """Test duplicate analysis against expected matches"""
    
    # Define expected matches
    expected_matches = [
        {'idx_a': 0, 'idx_b': 1, 'match_type': 'exact_normal', 'confidence_min': 90, 'confidence_max': 100, 'should_match': True},
        {'idx_a': 2, 'idx_b': 3, 'match_type': 'exact_swapped', 'confidence_min': 85, 'confidence_max': 95, 'should_match': True},
        {'idx_a': 4, 'idx_b': 5, 'match_type': 'fuzzy_normal', 'confidence_min': 70, 'confidence_max': 90, 'should_match': True},
        {'idx_a': 6, 'idx_b': 7, 'match_type': 'fuzzy_swapped', 'confidence_min': 65, 'confidence_max': 85, 'should_match': True},
        {'idx_a': 8, 'idx_b': 9, 'match_type': 'exact_normal', 'confidence_min': 90, 'confidence_max': 100, 'should_match': True},
        {'idx_a': 10, 'idx_b': 11, 'match_type': None, 'confidence_min': 0, 'confidence_max': 0, 'should_match': False},
        {'idx_a': 12, 'idx_b': 13, 'match_type': 'exact_normal', 'confidence_min': 90, 'confidence_max': 100, 'should_match': True},
        {'idx_a': 14, 'idx_b': 15, 'match_type': 'exact_normal', 'confidence_min': 90, 'confidence_max': 100, 'should_match': True},
        {'idx_a': 16, 'idx_b': 17, 'match_type': None, 'confidence_min': 0, 'confidence_max': 0, 'should_match': False},
        {'idx_a': 18, 'idx_b': 19, 'match_type': 'exact_normal', 'confidence_min': 90, 'confidence_max': 100, 'should_match': True},
        {'idx_a': 20, 'idx_b': 21, 'match_type': 'fuzzy_normal', 'confidence_min': 60, 'confidence_max': 80, 'should_match': True},
        {'idx_a': 22, 'idx_b': 23, 'match_type': 'fuzzy_normal', 'confidence_min': 70, 'confidence_max': 90, 'should_match': True},
        {'idx_a': 24, 'idx_b': 25, 'match_type': 'fuzzy_normal', 'confidence_min': 70, 'confidence_max': 90, 'should_match': True},
        {'idx_a': 26, 'idx_b': 27, 'match_type': 'fuzzy_normal', 'confidence_min': 70, 'confidence_max': 90, 'should_match': True},
        {'idx_a': 28, 'idx_b': 29, 'match_type': 'fuzzy_swapped', 'confidence_min': 70, 'confidence_max': 85, 'should_match': True},
    ]

    checker = UltraFastDuplicateChecker(fuzzy_threshold=0.75, use_parallel=False)
    matches = checker.analyze_duplicates(comprehensive_test_data, confidence_threshold=60.0)
    
    # Create lookup for actual matches
    actual_match_types = {}
    actual_confidences = {}
    
    for match in matches:
        key = (match.record_a_idx, match.record_b_idx)
        actual_match_types[key] = match.match_type
        actual_confidences[key] = match.confidence_score
    
    for expected in expected_matches:
        idx_pair = (expected['idx_a'], expected['idx_b'])
        
        if expected['should_match']:
            assert idx_pair in actual_match_types, f"Expected match for pair {idx_pair} but none found"

            actual_type = actual_match_types[idx_pair]
            actual_conf = actual_confidences[idx_pair]

            assert actual_type == expected['match_type'], \
                f"Pair {idx_pair}: Expected type {expected['match_type']}, got {actual_type}"

            assert expected['confidence_min'] <= actual_conf <= expected['confidence_max'], \
                f"Pair {idx_pair}: Expected confidence between {expected['confidence_min']} and {expected['confidence_max']}, got {actual_conf}"
        else:
            assert idx_pair not in actual_match_types, \
                f"Expected no match for pair {idx_pair}, but found {actual_match_types.get(idx_pair)}"

def test_extract_year():
    assert FastBusinessRules.extract_year('2022-01-01') == 2022
    assert FastBusinessRules.extract_year('01.01.2022') == 2022
    assert FastBusinessRules.extract_year(None) is None
    assert FastBusinessRules.extract_year('invalid') is None

def test_check_zweitname():
    assert FastBusinessRules.check_zweitname('Name', 'Zweit', 'Name', 'Zweit') is True
    assert FastBusinessRules.check_zweitname('Name', '', 'Name', '') is True
    assert FastBusinessRules.check_zweitname('Name', 'Zweit', 'Name', 'Diff') is False
    # Suffix check
    assert FastBusinessRules.check_zweitname('Name', '-Suffix', 'Name-Suffix', '') is True

def test_normalize_name():
    assert OptimizedFuzzyMatcher.normalize_name('Müller') == 'mueller'
    assert OptimizedFuzzyMatcher.normalize_name('Mueller') == 'mueller'
    assert OptimizedFuzzyMatcher.normalize_name('  Space  ') == 'space'
    assert OptimizedFuzzyMatcher.normalize_name(None) == ''
