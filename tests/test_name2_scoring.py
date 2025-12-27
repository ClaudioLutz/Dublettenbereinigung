"""
Test that name2 suffix matching gets high scores
"""
import pandas as pd
import numpy as np
from dedupe.preprocess import preprocess
from dedupe.scoring import score_pair


def test_name2_as_suffix():
    """
    Test case where name2 is part of the combined surname
    Example from user:
    - Record A: name="Haller", name2="-Bensel" 
    - Record B: name="Haller-Bensel", name2=""
    
    After preprocessing:
    - Record A: last="haller", name2="bensel"
    - Record B: last="haller bensel", name2=""
    
    These should match with high confidence (close to 100%)
    """
    # Create test data matching the user's example
    df = pd.DataFrame([
        {
            'Vorname': 'Hilde',
            'Name': 'Haller',
            'Name2': '-Bensel',
            'Strasse': 'Kammern',
            'HausNummer': '432',
            'Plz': '965000',
            'Ort': 'Nesslau',
            'Geburtstag': pd.NaT
        },
        {
            'Vorname': 'Hilde',
            'Name': 'Haller-Bensel',
            'Name2': '',
            'Strasse': 'Kammern',
            'HausNummer': '432',
            'Plz': '965000',
            'Ort': 'Nesslau',
            'Geburtstag': pd.NaT
        }
    ])
    
    # Preprocess
    cols = preprocess(df)
    
    # Score the pair
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80, enable_address_aware=True)
    
    # Assert match was found
    assert result is not None, "No match found - name2 suffix logic failed"
    
    # Assert high confidence score (should be 90+% since names match exactly and address matches)
    print(f"Score: {result.score:.1f}%")
    print(f"Name score: {result.name_score:.1f}%")
    print(f"Address score: {result.addr_score:.1f}%")
    print(f"Reason: {result.reason}")
    
    assert result.score >= 90.0, f"Score too low: {result.score:.1f}% (expected 90+%)"
    assert result.name_score >= 95.0, f"Name score too low: {result.name_score:.1f}% (expected 95+%)"
    assert result.reason == "exact_normal", f"Expected 'exact_normal', got '{result.reason}'"
    
    print("✓ Test passed: name2 suffix matching works correctly!")


def test_name2_different():
    """
    Test case where name2 values are different and should NOT match
    """
    df = pd.DataFrame([
        {
            'Vorname': 'Hilde',
            'Name': 'Haller',
            'Name2': '-Bensel',
            'Strasse': 'Kammern',
            'HausNummer': '432',
            'Plz': '965000',
            'Ort': 'Nesslau',
            'Geburtstag': pd.NaT
        },
        {
            'Vorname': 'Hilde',
            'Name': 'Haller',
            'Name2': '-Schmidt',
            'Strasse': 'Kammern',
            'HausNummer': '432',
            'Plz': '965000',
            'Ort': 'Nesslau',
            'Geburtstag': pd.NaT
        }
    ])
    
    # Preprocess
    cols = preprocess(df)
    
    # Score the pair
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80, enable_address_aware=True)
    
    # Assert NO match was found (different name2 values)
    assert result is None, "Match found but should be rejected due to different name2 values"
    
    print("✓ Test passed: different name2 values correctly rejected!")


def test_name2_both_empty():
    """
    Test case where both name2 are empty
    """
    df = pd.DataFrame([
        {
            'Vorname': 'Hilde',
            'Name': 'Haller',
            'Name2': '',
            'Strasse': 'Kammern',
            'HausNummer': '432',
            'Plz': '965000',
            'Ort': 'Nesslau',
            'Geburtstag': pd.NaT
        },
        {
            'Vorname': 'Hilde',
            'Name': 'Haller',
            'Name2': '',
            'Strasse': 'Kammern',
            'HausNummer': '432',
            'Plz': '965000',
            'Ort': 'Nesslau',
            'Geburtstag': pd.NaT
        }
    ])
    
    # Preprocess
    cols = preprocess(df)
    
    # Score the pair
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80, enable_address_aware=True)
    
    # Assert match was found
    assert result is not None, "No match found"
    assert result.score >= 90.0, f"Score too low: {result.score:.1f}%"
    
    print("✓ Test passed: both name2 empty works correctly!")


if __name__ == '__main__':
    print("Testing name2 suffix scoring fix...\n")
    
    test_name2_as_suffix()
    print()
    
    test_name2_different()
    print()
    
    test_name2_both_empty()
    print()
    
    print("All tests passed! ✓")
