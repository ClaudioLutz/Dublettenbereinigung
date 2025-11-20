"""
Test Script to Verify Restored Business Logic
==============================================

Tests the two-stage architecture with proper confidence scoring
and verifies all business rules are working correctly.
"""

import pandas as pd
from duplicate_checker_optimized import UltraFastDuplicateChecker
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_comprehensive_test_data() -> pd.DataFrame:
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
        
        # Test 21: No match case (completely different record)
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

def verify_match_expectations(matches, expected_matches):
    """Verify that matches meet expectations"""
    
    results = {
        'total_tests': len(expected_matches),
        'passed': 0,
        'failed': 0,
        'failures': []
    }
    
    # Create lookup for actual matches
    actual_match_types = {}
    actual_confidences = {}
    
    for match in matches:
        key = (match.record_a_idx, match.record_b_idx)
        actual_match_types[key] = match.match_type
        actual_confidences[key] = match.confidence_score
    
    # Check expectations
    for expected in expected_matches:
        test_name = expected['test_name']
        idx_pair = (expected['idx_a'], expected['idx_b'])
        expected_type = expected['match_type']
        expected_conf_min = expected['confidence_min']
        expected_conf_max = expected['confidence_max']
        should_match = expected['should_match']
        
        if should_match:
            if idx_pair in actual_match_types:
                actual_type = actual_match_types[idx_pair]
                actual_conf = actual_confidences[idx_pair]
                
                # Check match type
                type_ok = (actual_type == expected_type)
                
                # Check confidence range
                conf_ok = (expected_conf_min <= actual_conf <= expected_conf_max)
                
                if type_ok and conf_ok:
                    results['passed'] += 1
                    logger.info(f"✓ PASS: {test_name} - {actual_type} @ {actual_conf:.1f}%")
                else:
                    results['failed'] += 1
                    failure_msg = f"✗ FAIL: {test_name} - Expected {expected_type} ({expected_conf_min}-{expected_conf_max}%), got {actual_type} @ {actual_conf:.1f}%"
                    results['failures'].append(failure_msg)
                    logger.error(failure_msg)
            else:
                results['failed'] += 1
                failure_msg = f"✗ FAIL: {test_name} - Expected match but none found"
                results['failures'].append(failure_msg)
                logger.error(failure_msg)
        else:
            # Should NOT match
            if idx_pair not in actual_match_types:
                results['passed'] += 1
                logger.info(f"✓ PASS: {test_name} - Correctly rejected")
            else:
                results['failed'] += 1
                actual_type = actual_match_types[idx_pair]
                actual_conf = actual_confidences[idx_pair]
                failure_msg = f"✗ FAIL: {test_name} - Should not match but found {actual_type} @ {actual_conf:.1f}%"
                results['failures'].append(failure_msg)
                logger.error(failure_msg)
    
    return results

def main():
    """Run comprehensive tests"""
    
    print("=" * 80)
    print("Testing Restored Business Logic - Two-Stage Architecture")
    print("=" * 80)
    print()
    
    # Create test data
    df = create_comprehensive_test_data()
    print(f"Created test dataset with {len(df)} records")
    print()
    
    # Define expected matches
    expected_matches = [
        {'test_name': 'Exact Normal Match', 'idx_a': 0, 'idx_b': 1, 'match_type': 'exact_normal', 'confidence_min': 90, 'confidence_max': 100, 'should_match': True},
        {'test_name': 'Exact Swapped Match', 'idx_a': 2, 'idx_b': 3, 'match_type': 'exact_swapped', 'confidence_min': 85, 'confidence_max': 95, 'should_match': True},
        {'test_name': 'Fuzzy Normal Match', 'idx_a': 4, 'idx_b': 5, 'match_type': 'fuzzy_normal', 'confidence_min': 70, 'confidence_max': 90, 'should_match': True},
        {'test_name': 'Fuzzy Swapped Match', 'idx_a': 6, 'idx_b': 7, 'match_type': 'fuzzy_swapped', 'confidence_min': 65, 'confidence_max': 85, 'should_match': True},
        {'test_name': 'German Umlaut Match', 'idx_a': 8, 'idx_b': 9, 'match_type': 'exact_normal', 'confidence_min': 90, 'confidence_max': 100, 'should_match': True},
        {'test_name': 'Zweitname Violation', 'idx_a': 10, 'idx_b': 11, 'match_type': None, 'confidence_min': 0, 'confidence_max': 0, 'should_match': False},
        {'test_name': 'Zweitname Pass (Case Insensitive)', 'idx_a': 12, 'idx_b': 13, 'match_type': 'exact_normal', 'confidence_min': 90, 'confidence_max': 100, 'should_match': True},
        {'test_name': 'Date Rule (Geburtstag vs Jahrgang)', 'idx_a': 14, 'idx_b': 15, 'match_type': 'exact_normal', 'confidence_min': 90, 'confidence_max': 100, 'should_match': True},
        {'test_name': 'Date Rule Violation', 'idx_a': 16, 'idx_b': 17, 'match_type': None, 'confidence_min': 0, 'confidence_max': 0, 'should_match': False},
        {'test_name': 'Rule 4 (Geburtstag Precedence)', 'idx_a': 18, 'idx_b': 19, 'match_type': 'exact_normal', 'confidence_min': 90, 'confidence_max': 100, 'should_match': True},
    ]
    
    # Initialize checker
    checker = UltraFastDuplicateChecker(fuzzy_threshold=0.7, use_parallel=False)
    
    # Run analysis
    print("Running duplicate analysis...")
    matches = checker.analyze_duplicates(df, confidence_threshold=60.0)
    print()
    
    print(f"Found {len(matches)} matches")
    print()
    
    # Display all matches
    print("=" * 80)
    print("All Detected Matches")
    print("=" * 80)
    for i, match in enumerate(matches, 1):
        record_a = df.iloc[match.record_a_idx]
        record_b = df.iloc[match.record_b_idx]
        
        print(f"\nMatch {i}: {match.match_type.upper()} (Confidence: {match.confidence_score:.1f}%)")
        print(f"  A [{match.record_a_idx}]: {record_a['Vorname']} {record_a['Name']} - {record_a['TestCase']}")
        print(f"  B [{match.record_b_idx}]: {record_b['Vorname']} {record_b['Name']} - {record_b['TestCase']}")
    
    print()
    print("=" * 80)
    print("Test Results")
    print("=" * 80)
    print()
    
    # Verify expectations
    results = verify_match_expectations(matches, expected_matches)
    
    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total Tests: {results['total_tests']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {results['passed']/results['total_tests']*100:.1f}%")
    
    if results['failed'] > 0:
        print()
        print("Failed Tests:")
        for failure in results['failures']:
            print(f"  {failure}")
    
    print()
    
    # Export results for inspection
    if matches:
        checker.export_results(matches, df, 'test_results.csv')
        print("Results exported to test_results.csv")
    
    print()
    print("=" * 80)
    
    return results['failed'] == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
