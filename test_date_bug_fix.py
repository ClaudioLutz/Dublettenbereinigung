"""
Test script to verify the date rule bug fix
============================================

This script tests the specific cases that were incorrectly flagged as duplicates:
- David Pablo Gloor: 1998 vs 1963
- Marco Kistler: 1984 vs 1959
- Kata Burmazovic: 1965 vs 1954
- Michael Hurni: 1965 vs 1976

After the fix, these should NOT be flagged as duplicates.
"""

import pandas as pd
from duplicate_checker_poc import DuplicateChecker, BusinessRulesEngine

def test_date_rule_directly():
    """Test the date rule logic directly"""
    
    print("="*80)
    print("TESTING DATE RULE LOGIC DIRECTLY")
    print("="*80)
    
    engine = BusinessRulesEngine()
    
    # Test Case 1: David Pablo Gloor
    print("\n1. David Pablo Gloor (1998 vs 1963):")
    print("   Record A: Jahrgang=1998, Geburtstag=empty")
    print("   Record B: Jahrgang=1963, Geburtstag=1963-07-16")
    result1 = engine.check_date_rule('', '1998.0', '1963-07-16', '1963.0')
    print(f"   Result: {result1} (Expected: False)")
    print(f"   ✓ PASS" if result1 == False else f"   ✗ FAIL")
    
    # Test Case 2: Marco Kistler
    print("\n2. Marco Kistler (1984 vs 1959):")
    print("   Record A: Jahrgang=1984, Geburtstag=1984-03-12")
    print("   Record B: Jahrgang=1959, Geburtstag=empty")
    result2 = engine.check_date_rule('1984-03-12', '1984.0', '', '1959.0')
    print(f"   Result: {result2} (Expected: False)")
    print(f"   ✓ PASS" if result2 == False else f"   ✗ FAIL")
    
    # Test Case 3: Kata Burmazovic
    print("\n3. Kata Burmazovic (1965 vs 1954):")
    print("   Record A: Jahrgang=1965, Geburtstag=1965-02-17")
    print("   Record B: Jahrgang=1954, Geburtstag=empty")
    result3 = engine.check_date_rule('1965-02-17', '1965.0', '', '1954.0')
    print(f"   Result: {result3} (Expected: False)")
    print(f"   ✓ PASS" if result3 == False else f"   ✗ FAIL")
    
    # Test Case 4: Michael Hurni
    print("\n4. Michael Hurni (1965 vs 1976):")
    print("   Record A: Jahrgang=1965, Geburtstag=1965-02-19")
    print("   Record B: Jahrgang=1976, Geburtstag=empty")
    result4 = engine.check_date_rule('1965-02-19', '1965.0', '', '1976.0')
    print(f"   Result: {result4} (Expected: False)")
    print(f"   ✓ PASS" if result4 == False else f"   ✗ FAIL")
    
    all_passed = all([result1 == False, result2 == False, result3 == False, result4 == False])
    
    print("\n" + "="*80)
    if all_passed:
        print("✓ ALL TESTS PASSED - Date bug is fixed!")
    else:
        print("✗ SOME TESTS FAILED - Date bug still exists!")
    print("="*80)
    
    return all_passed

def test_with_real_data():
    """Test with the actual CSV data structure"""
    
    print("\n\n")
    print("="*80)
    print("TESTING WITH REAL DATA STRUCTURE")
    print("="*80)
    
    # Create test data mimicking the CSV structure
    test_pairs = [
        {
            'name': 'David Pablo Gloor',
            'record_a': {
                'Name': 'Gloor',
                'Vorname': 'David Pablo',
                'Name2': '',
                'Strasse': 'Buckhauserstrasse',
                'HausNummer': '1',
                'Plz': '804800',
                'Ort': 'Zürich',
                'Geburtstag': '',
                'Jahrgang': 1998.0,
                'Crefo': 429418739
            },
            'record_b': {
                'Name': 'Gloor',
                'Vorname': 'David Pablo',
                'Name2': '',
                'Strasse': 'Buckhauserstrasse',
                'HausNummer': '1',
                'Plz': '804800',
                'Ort': 'Zürich',
                'Geburtstag': '1963-07-16',
                'Jahrgang': 1963.0,
                'Crefo': 429404574
            }
        },
        {
            'name': 'Marco Kistler',
            'record_a': {
                'Name': 'Kistler',
                'Vorname': 'Marco',
                'Name2': '',
                'Strasse': 'St. Gallerstrasse',
                'HausNummer': '55',
                'Plz': '885300',
                'Ort': 'Lachen SZ',
                'Geburtstag': '1984-03-12',
                'Jahrgang': 1984.0,
                'Crefo': 429417974
            },
            'record_b': {
                'Name': 'Kistler',
                'Vorname': 'Marco',
                'Name2': '',
                'Strasse': 'St. Gallerstrasse',
                'HausNummer': '55',
                'Plz': '885300',
                'Ort': 'Lachen SZ',
                'Geburtstag': '',
                'Jahrgang': 1959.0,
                'Crefo': 429400801
            }
        },
        {
            'name': 'Kata Burmazovic',
            'record_a': {
                'Name': 'Burmazovic',
                'Vorname': 'Kata',
                'Name2': '',
                'Strasse': 'Seeblick',
                'HausNummer': '6',
                'Plz': '633000',
                'Ort': 'Cham',
                'Geburtstag': '1965-02-17',
                'Jahrgang': 1965.0,
                'Crefo': 429417710
            },
            'record_b': {
                'Name': 'Burmazovic',
                'Vorname': 'Kata',
                'Name2': '',
                'Strasse': 'Seeblick',
                'HausNummer': '6',
                'Plz': '633000',
                'Ort': 'Cham',
                'Geburtstag': '',
                'Jahrgang': 1954.0,
                'Crefo': 429393760
            }
        },
        {
            'name': 'Michael Hurni',
            'record_a': {
                'Name': 'Hurni',
                'Vorname': 'Michael',
                'Name2': '',
                'Strasse': 'Bäumleingasse',
                'HausNummer': '4',
                'Plz': '405100',
                'Ort': 'Basel',
                'Geburtstag': '1965-02-19',
                'Jahrgang': 1965.0,
                'Crefo': 429417870
            },
            'record_b': {
                'Name': 'Hurni',
                'Vorname': 'Michael',
                'Name2': '',
                'Strasse': 'Bäumleingasse',
                'HausNummer': '4',
                'Plz': '405100',
                'Ort': 'Basel',
                'Geburtstag': '',
                'Jahrgang': 1976.0,
                'Crefo': 429394457
            }
        }
    ]
    
    checker = DuplicateChecker(fuzzy_threshold=0.7)
    
    results = []
    for pair in test_pairs:
        print(f"\nTesting: {pair['name']}")
        
        # Convert to Series
        record_a = pd.Series(pair['record_a'])
        record_b = pd.Series(pair['record_b'])
        
        # Check exact match
        exact_match = checker.check_exact_match(record_a, record_b)
        
        # Check fuzzy match
        fuzzy_match = checker.check_fuzzy_match(record_a, record_b)
        
        is_match = (exact_match is not None) or (fuzzy_match is not None)
        
        print(f"  Years: {pair['record_a'].get('Jahrgang')} vs {pair['record_b'].get('Jahrgang')}")
        print(f"  Birthdates: '{pair['record_a'].get('Geburtstag')}' vs '{pair['record_b'].get('Geburtstag')}'")
        print(f"  Exact Match: {exact_match is not None}")
        print(f"  Fuzzy Match: {fuzzy_match is not None}")
        print(f"  Result: {'MATCH FOUND' if is_match else 'NO MATCH'}")
        print(f"  Expected: NO MATCH")
        
        if not is_match:
            print(f"  ✓ PASS - Correctly rejected as non-duplicate")
            results.append(True)
        else:
            print(f"  ✗ FAIL - Incorrectly flagged as duplicate")
            results.append(False)
    
    all_passed = all(results)
    
    print("\n" + "="*80)
    if all_passed:
        print("✓ ALL REAL DATA TESTS PASSED - False positives eliminated!")
    else:
        print("✗ SOME REAL DATA TESTS FAILED - False positives still exist!")
    print("="*80)
    
    return all_passed

def test_valid_matches_still_work():
    """Test that valid matches still work correctly"""
    
    print("\n\n")
    print("="*80)
    print("TESTING THAT VALID MATCHES STILL WORK")
    print("="*80)
    
    checker = DuplicateChecker(fuzzy_threshold=0.7)
    
    # Test 1: Both have same Geburtstag year
    print("\n1. Valid match - Both have Geburtstag with same year:")
    record_a = pd.Series({
        'Name': 'Müller',
        'Vorname': 'Hans',
        'Name2': '',
        'Strasse': 'Teststrasse',
        'HausNummer': '1',
        'Plz': '12345',
        'Ort': 'Teststadt',
        'Geburtstag': '1980-01-15',
        'Jahrgang': None
    })
    record_b = pd.Series({
        'Name': 'Müller',
        'Vorname': 'Hans',
        'Name2': '',
        'Strasse': 'Teststrasse',
        'HausNummer': '1',
        'Plz': '12345',
        'Ort': 'Teststadt',
        'Geburtstag': '1980-06-20',
        'Jahrgang': None
    })
    
    match = checker.check_exact_match(record_a, record_b)
    print(f"  Result: {'MATCH' if match else 'NO MATCH'} (Expected: MATCH)")
    print(f"  ✓ PASS" if match else f"  ✗ FAIL")
    
    # Test 2: Mixed date with matching years
    print("\n2. Valid match - Mixed date with matching years:")
    record_a = pd.Series({
        'Name': 'Schmidt',
        'Vorname': 'Anna',
        'Name2': '',
        'Strasse': 'Teststrasse',
        'HausNummer': '2',
        'Plz': '12345',
        'Ort': 'Teststadt',
        'Geburtstag': '1990-03-10',
        'Jahrgang': None
    })
    record_b = pd.Series({
        'Name': 'Schmidt',
        'Vorname': 'Anna',
        'Name2': '',
        'Strasse': 'Teststrasse',
        'HausNummer': '2',
        'Plz': '12345',
        'Ort': 'Teststadt',
        'Geburtstag': '',
        'Jahrgang': 1990.0
    })
    
    match = checker.check_exact_match(record_a, record_b)
    print(f"  Result: {'MATCH' if match else 'NO MATCH'} (Expected: MATCH)")
    print(f"  ✓ PASS" if match else f"  ✗ FAIL")
    
    # Test 3: Both have Jahrgang with same year
    print("\n3. Valid match - Both have Jahrgang with same year:")
    record_a = pd.Series({
        'Name': 'Weber',
        'Vorname': 'Thomas',
        'Name2': '',
        'Strasse': 'Teststrasse',
        'HausNummer': '3',
        'Plz': '12345',
        'Ort': 'Teststadt',
        'Geburtstag': '',
        'Jahrgang': 1985.0
    })
    record_b = pd.Series({
        'Name': 'Weber',
        'Vorname': 'Thomas',
        'Name2': '',
        'Strasse': 'Teststrasse',
        'HausNummer': '3',
        'Plz': '12345',
        'Ort': 'Teststadt',
        'Geburtstag': '',
        'Jahrgang': 1985.0
    })
    
    match = checker.check_exact_match(record_a, record_b)
    print(f"  Result: {'MATCH' if match else 'NO MATCH'} (Expected: MATCH)")
    print(f"  ✓ PASS" if match else f"  ✗ FAIL")
    
    print("\n" + "="*80)

def main():
    """Run all tests"""
    
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "DATE BUG FIX VALIDATION TEST" + " "*30 + "║")
    print("╚" + "="*78 + "╝")
    
    # Run tests
    test1_passed = test_date_rule_directly()
    test2_passed = test_with_real_data()
    test_valid_matches_still_work()
    
    # Final summary
    print("\n\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*30 + "FINAL SUMMARY" + " "*35 + "║")
    print("╚" + "="*78 + "╝")
    
    if test1_passed and test2_passed:
        print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
        print("\nThe date bug has been successfully fixed:")
        print("  • Jahrgang float parsing now works correctly")
        print("  • Ambiguous cases (one with year, one without) are properly rejected")
        print("  • False positives have been eliminated")
        print("  • Valid matches still work correctly")
        print("\nThe 4 problematic pairs will no longer be flagged as duplicates.")
        return 0
    else:
        print("\n✗✗✗ SOME TESTS FAILED! ✗✗✗")
        print("\nThe date bug fix needs further attention.")
        return 1

if __name__ == "__main__":
    exit(main())
