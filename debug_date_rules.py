"""
Debug script to test the specific date rules issue mentioned by user
"""

import pandas as pd
from duplicate_checker_poc import BusinessRulesEngine

def test_specific_case():
    """Test the specific case mentioned by user"""
    
    # Record A: empty geburtstag, jahrgang 1998
    geburtstag_a = ''
    jahrgang_a = '1998'
    
    # Record B: geburtstag 16.07.1963, jahrgang 1963  
    geburtstag_b = '16.07.1963'
    jahrgang_b = '1963'
    
    # Test the rule
    result = BusinessRulesEngine.check_date_rule(
        geburtstag_a, jahrgang_a,
        geburtstag_b, jahrgang_b
    )
    
    print("=== DEBUGGING DATE RULES ===")
    print(f"Record A: geburtstag='{geburtstag_a}', jahrgang='{jahrgang_a}'")
    print(f"Record B: geburtstag='{geburtstag_b}', jahrgang='{jahrgang_b}'")
    print(f"Rule result: {result}")
    print()
    
    # Debug the internal logic
    year_a = BusinessRulesEngine.extract_year_from_date(geburtstag_a)
    year_b = BusinessRulesEngine.extract_year_from_date(geburtstag_b)
    
    jg_a = None
    jg_b = None
    
    try:
        if jahrgang_a and not pd.isna(jahrgang_a):
            jg_a = int(str(jahrgang_a).strip())
    except:
        jg_a = None
        
    try:
        if jahrgang_b and not pd.isna(jahrgang_b):
            jg_b = int(str(jahrgang_b).strip())
    except:
        jg_b = None
    
    print("=== INTERNAL VALUES ===")
    print(f"year_a: {year_a}")
    print(f"year_b: {year_b}")
    print(f"jg_a: {jg_a}")
    print(f"jg_b: {jg_b}")
    print()
    
    # Rule 4: If a record has both geburtstag and jahrgang, ignore jahrgang
    effective_year_a = year_a if year_a else jg_a
    effective_year_b = year_b if year_b else jg_b
    
    print("=== EFFECTIVE YEARS ===")
    print(f"effective_year_a: {effective_year_a}")
    print(f"effective_year_b: {effective_year_b}")
    print()
    
    # Now compare effective years
    if effective_year_a and effective_year_b:
        should_match = effective_year_a == effective_year_b
        print(f"Both effective years exist: {effective_year_a} == {effective_year_b} = {should_match}")
    else:
        print("One or both effective years missing - rule passes by default")
    
    print()
    print("=== EXPECTED BEHAVIOR ===")
    print("Record A: empty geburtstag + jahrgang 1998 = effective_year 1998")
    print("Record B: geburtstag 1963 + jahrgang 1963 = effective_year 1963 (jahrgang ignored)")
    print("1998 != 1963, so these should NOT match (should return False)")

if __name__ == "__main__":
    test_specific_case()
