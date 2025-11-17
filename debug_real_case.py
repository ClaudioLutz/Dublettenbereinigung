"""
Debug the exact real case that's still failing
"""

import pandas as pd
from duplicate_checker_poc import BusinessRulesEngine

def debug_real_case():
    """Debug the exact case from user's CSV output"""
    
    print("=== DEBUGGING REAL CASE FROM CSV ===")
    
    # Exact data from user's CSV
    record_a = {
        'Name': 'Gloor',
        'Vorname': 'David Pablo', 
        'Name2': '',
        'Strasse': 'Buckhauserstrasse',
        'HausNummer': '1',
        'Plz': '804800',
        'Ort': 'Zürich',
        'Crefo': '429418739',
        'Geburtstag': '',  # Empty string from CSV
        'Jahrgang': '1998',
    }
    
    record_b = {
        'Name': 'Gloor',
        'Vorname': 'David Pablo',
        'Name2': '',
        'Strasse': 'Buckhauserstrasse', 
        'HausNummer': '1',
        'Plz': '804800',
        'Ort': 'Zürich',
        'Crefo': '429404574',
        'Geburtstag': '16.07.1963',  # From CSV
        'Jahrgang': '1963',
    }
    
    print("Record A:")
    print(f"  Geburtstag: '{record_a['Geburtstag']}' (type: {type(record_a['Geburtstag'])})")
    print(f"  Jahrgang: '{record_a['Jahrgang']}' (type: {type(record_a['Jahrgang'])})")
    
    print("Record B:")
    print(f"  Geburtstag: '{record_b['Geburtstag']}' (type: {type(record_b['Geburtstag'])})")
    print(f"  Jahrgang: '{record_b['Jahrgang']}' (type: {type(record_b['Jahrgang'])})")
    print()
    
    # Test the business rule directly
    result = BusinessRulesEngine.check_date_rule(
        record_a['Geburtstag'], record_a['Jahrgang'],
        record_b['Geburtstag'], record_b['Jahrgang']
    )
    
    print(f"Business Rules Result: {result}")
    print()
    
    # Debug step by step
    year_a = BusinessRulesEngine.extract_year_from_date(record_a['Geburtstag'])
    year_b = BusinessRulesEngine.extract_year_from_date(record_b['Geburtstag'])
    
    jg_a = None
    jg_b = None
    
    try:
        if record_a['Jahrgang'] and not pd.isna(record_a['Jahrgang']):
            jg_a = int(str(record_a['Jahrgang']).strip())
    except:
        jg_a = None
        
    try:
        if record_b['Jahrgang'] and not pd.isna(record_b['Jahrgang']):
            jg_b = int(str(record_b['Jahrgang']).strip())
    except:
        jg_b = None
    
    print("=== STEP-BY-STEP DEBUG ===")
    print(f"year_a: {year_a}")
    print(f"year_b: {year_b}")
    print(f"jg_a: {jg_a}")
    print(f"jg_b: {jg_b}")
    print()
    
    effective_year_a = year_a if year_a else jg_a
    effective_year_b = year_b if year_b else jg_b
    
    print(f"effective_year_a: {effective_year_a}")
    print(f"effective_year_b: {effective_year_b}")
    print()
    
    if effective_year_a and effective_year_b:
        final_result = effective_year_a == effective_year_b
        print(f"Final comparison: {effective_year_a} == {effective_year_b} = {final_result}")
    else:
        print("One or both effective years missing - rule passes by default")
        final_result = True
    
    print()
    print("=== EXPECTATION ===")
    print("Should be: 1998 == 1963 = False")
    print(f"Actually is: {final_result}")
    print(f"FIX WORKING: {final_result == False}")

if __name__ == "__main__":
    debug_real_case()
