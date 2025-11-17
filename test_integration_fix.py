"""
Test script to verify the date rules fix in integration
"""

import pandas as pd
from duplicate_checker_integration import DuplicateCheckerIntegration

def test_integration_with_problem_case():
    """Test integration with the specific problematic case"""
    
    # Create test data with the problematic case
    test_data = [
        # Record A: empty geburtstag, jahrgang 1998
        {
            'Name': 'Gloor',
            'Vorname': 'David Pablo',
            'Name2': '',
            'Strasse': 'Buckhauserstrasse',
            'HausNummer': '1',
            'Plz': '804800',
            'Ort': 'Zürich',
            'Crefo': '429418739',
            'Geburtstag': '',  # Empty
            'Jahrgang': '1998',
            'Erfasst': '2025-10-18 02:58:10.012223',
            'Quelle_95': '0'
        },
        # Record B: geburtstag 16.07.1963, jahrgang 1963  
        {
            'Name': 'Gloor',
            'Vorname': 'David Pablo',
            'Name2': '',
            'Strasse': 'Buckhauserstrasse',
            'HausNummer': '1',
            'Plz': '804800',
            'Ort': 'Zürich',
            'Crefo': '429404574',
            'Geburtstag': '16.07.1963',  # Birth date year 1963
            'Jahrgang': '1963',  # Should be ignored due to Rule 4
            'Erfasst': '2025-10-17 23:36:17.864359',
            'Quelle_95': '0'
        }
    ]
    
    df = pd.DataFrame(test_data)
    integration = DuplicateCheckerIntegration(fuzzy_threshold=0.7, use_parallel=False)
    
    print("=== TESTING INTEGRATION WITH PROBLEMATIC CASE ===")
    print("Test Data:")
    for i, row in df.iterrows():
        print(f"Record {i}: {row['Vorname']} {row['Name']}")
        print(f"  Geburtstag: '{row['Geburtstag']}'")
        print(f"  Jahrgang: '{row['Jahrgang']}'")
        print(f"  Crefo: {row['Crefo']}")
        print()
    
    # Analyze duplicates
    matches = integration.analyze_duplicates(df, confidence_threshold=60.0)
    
    print(f"Found {len(matches)} potential duplicates:")
    
    if matches:
        for i, match in enumerate(matches, 1):
            record_a = df.iloc[match.record_a_idx]
            record_b = df.iloc[match.record_b_idx]
            
            print(f"\nMatch {i}: {match.match_type.upper()} (Confidence: {match.confidence_score:.1f}%)")
            print(f"Record A (Index {match.record_a_idx}): {record_a['Vorname']} {record_a['Name']} - Crefo: {record_a['Crefo']}")
            print(f"  Geburtstag: '{record_a['Geburtstag']}', Jahrgang: '{record_a['Jahrgang']}'")
            print(f"Record B (Index {match.record_b_idx}): {record_b['Vorname']} {record_b['Name']} - Crefo: {record_b['Crefo']}")
            print(f"  Geburtstag: '{record_b['Geburtstag']}', Jahrgang: '{record_b['Jahrgang']}'")
    else:
        print("NO MATCHES FOUND - This is CORRECT behavior!")
    
    print("\n=== EXPECTED RESULT ===")
    print("These records should NOT match because:")
    print("- Record A effective year: 1998 (from Jahrgang)")
    print("- Record B effective year: 1963 (from Geburtstag, Jahrgang ignored)")
    print("- 1998 ≠ 1963, so no match should be found")

if __name__ == "__main__":
    test_integration_with_problem_case()
