"""
Test strict fuzzy matching rules with real problem cases.
"""
import pandas as pd
import sys
sys.path.insert(0, 'c:\\Lokal_Code\\dubletten')

from dedupe.preprocess import preprocess
from dedupe.scoring import score_pair


def test_case_1_michaela():
    """
    Case 1: Michaela Asri (has DOB) vs Michaela Rabbani Mughal (no DOB)
    Same address but one DOB missing - should score much lower or reject
    """
    print("\n" + "="*80)
    print("TEST CASE 1: Michaela Asri vs Michaela Rabbani Mughal")
    print("Issue: One DOB missing, should be stricter")
    print("="*80)
    
    df = pd.DataFrame([
        {
            'idx': 3023,
            'vorname': 'Michaela',
            'name': 'Asri',
            'name2': '',
            'strasse': 'Vonwilstrasse',
            'haus': '1',
            'plz': '900000',
            'ort': 'St. Gallen',
            'pnr': 423735720,
            'geburtsdatum': '1972-10-27',
            'jahrgang': 1972.0
        },
        {
            'idx': 3040,
            'vorname': 'Michaela',
            'name': 'Rabbani Mughal',
            'name2': '',
            'strasse': 'Vonwilstrasse',
            'haus': '1',
            'plz': '900000',
            'ort': 'St. Gallen',
            'pnr': 428954512,
            'geburtsdatum': None,
            'jahrgang': None
        }
    ])
    
    # Rename columns to match expected format
    df = df.rename(columns={
        'vorname': 'Vorname',
        'name': 'Name',
        'name2': 'Name2',
        'strasse': 'Strasse',
        'haus': 'HausNummer',
        'plz': 'Plz',
        'ort': 'Ort',
        'geburtsdatum': 'Geburtstag',
        'jahrgang': 'Jahrgang'
    })
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80)
    
    print(f"\nRecord A: Michaela Asri, DOB=1972-10-27, Vonwilstrasse 1")
    print(f"Record B: Michaela Rabbani Mughal, DOB=None, Vonwilstrasse 1")
    
    if result:
        print(f"\n✓ Match found:")
        print(f"  Score: {result.score:.2f}")
        print(f"  Name Score: {result.name_score:.2f}")
        print(f"  Address Score: {result.addr_score:.2f}")
        print(f"  Reason: {result.reason}")
        print(f"\n⚠️ EXPECTED: Should reject or score much lower (was 72.21)")
    else:
        print(f"\n✓ REJECTED (as expected - one DOB missing)")


def test_case_2_tschannen():
    """
    Case 2: Dominique Tschannen vs Doris Tschannen (both have YOB 1976, no DOB)
    Birth year alone is insufficient - should reject
    """
    print("\n" + "="*80)
    print("TEST CASE 2: Dominique Tschannen vs Doris Tschannen")
    print("Issue: YOB-only match (1976), different first names, should reject")
    print("="*80)
    
    df = pd.DataFrame([
        {
            'idx': 2949,
            'vorname': 'Dominique',
            'name': 'Tschannen',
            'name2': '',
            'strasse': 'Vonwilstrasse',
            'haus': '27',
            'plz': '900000',
            'ort': 'St. Gallen',
            'pnr': 420802304,
            'geburtsdatum': None,
            'jahrgang': 1976.0
        },
        {
            'idx': 3002,
            'vorname': 'Doris',
            'name': 'Tschannen',
            'name2': '',
            'strasse': 'Vonwilstrasse',
            'haus': '27',
            'plz': '900000',
            'ort': 'St. Gallen',
            'pnr': 420991330,
            'geburtsdatum': None,
            'jahrgang': 1976.0
        }
    ])
    
    # Rename columns to match expected format
    df = df.rename(columns={
        'vorname': 'Vorname',
        'name': 'Name',
        'name2': 'Name2',
        'strasse': 'Strasse',
        'haus': 'HausNummer',
        'plz': 'Plz',
        'ort': 'Ort',
        'geburtsdatum': 'Geburtstag',
        'jahrgang': 'Jahrgang'
    })
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80)
    
    print(f"\nRecord A: Dominique Tschannen, YOB=1976, Vonwilstrasse 27")
    print(f"Record B: Doris Tschannen, YOB=1976, Vonwilstrasse 27")
    
    if result:
        print(f"\n✗ Match found:")
        print(f"  Score: {result.score:.2f}")
        print(f"  Name Score: {result.name_score:.2f}")
        print(f"  Address Score: {result.addr_score:.2f}")
        print(f"  Reason: {result.reason}")
        print(f"\n⚠️ EXPECTED: Should reject (was 70.0)")
    else:
        print(f"\n✓ REJECTED (as expected - YOB-only match, different first names)")


def test_case_3_amsler_schmid():
    """
    Case 3: René Amsler vs Renate Schmid (different house numbers)
    Different last names, different house numbers - should reject
    """
    print("\n" + "="*80)
    print("TEST CASE 3: René Amsler vs Renate Schmid")
    print("Issue: Different names, different house numbers (17d vs 17c), should reject")
    print("="*80)
    
    df = pd.DataFrame([
        {
            'idx': 3215,
            'vorname': 'René',
            'name': 'Amsler',
            'name2': '-Schmid',
            'strasse': 'Varnbüelstrasse',
            'haus': '17d',
            'plz': '900000',
            'ort': 'St. Gallen',
            'pnr': 402528952,
            'geburtsdatum': '1955-07-01',
            'jahrgang': 1955.0
        },
        {
            'idx': 3227,
            'vorname': 'Renate',
            'name': 'Schmid',
            'name2': '',
            'strasse': 'Varnbüelstrasse',
            'haus': '17c',
            'plz': '900000',
            'ort': 'St. Gallen',
            'pnr': 428933279,
            'geburtsdatum': None,
            'jahrgang': None
        }
    ])
    
    # Rename columns to match expected format
    df = df.rename(columns={
        'vorname': 'Vorname',
        'name': 'Name',
        'name2': 'Name2',
        'strasse': 'Strasse',
        'haus': 'HausNummer',
        'plz': 'Plz',
        'ort': 'Ort',
        'geburtsdatum': 'Geburtstag',
        'jahrgang': 'Jahrgang'
    })
    
    cols = preprocess(df)
    result = score_pair(0, 1, cols, fuzzy_threshold=0.80)
    
    print(f"\nRecord A: René Amsler-Schmid, DOB=1955-07-01, Varnbüelstrasse 17d")
    print(f"Record B: Renate Schmid, DOB=None, Varnbüelstrasse 17c")
    
    if result:
        print(f"\n✗ Match found:")
        print(f"  Score: {result.score:.2f}")
        print(f"  Name Score: {result.name_score:.2f}")
        print(f"  Address Score: {result.addr_score:.2f}")
        print(f"  Reason: {result.reason}")
        print(f"\n⚠️ EXPECTED: Should reject (was 65.0)")
    else:
        print(f"\n✓ REJECTED (as expected - different house numbers)")


if __name__ == '__main__':
    print("\n" + "#"*80)
    print("# TESTING STRICT FUZZY MATCHING RULES")
    print("# DOB and Address must be exact matches for fuzzy name matches")
    print("#"*80)
    
    test_case_1_michaela()
    test_case_2_tschannen()
    test_case_3_amsler_schmid()
    
    print("\n" + "#"*80)
    print("# TEST SUMMARY")
    print("#"*80)
    print("All three cases should now be REJECTED due to:")
    print("1. One DOB missing (Michaela case)")
    print("2. YOB-only match with different first names (Tschannen case)")
    print("3. Different house numbers + one DOB missing (Amsler/Schmid case)")
    print("#"*80 + "\n")
