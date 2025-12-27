"""
Verify the name2 scoring fix on the user's actual example
"""
import pandas as pd
from dedupe.preprocess import preprocess
from dedupe.scoring import score_pair


# Recreate the exact data from the user's example
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

print("=" * 70)
print("BEFORE FIX: Score was 77.5%")
print("=" * 70)
print()
print("Record A:")
print(f"  Vorname: {df.iloc[0]['Vorname']}")
print(f"  Name: {df.iloc[0]['Name']}")
print(f"  Name2: {df.iloc[0]['Name2']}")
print(f"  Strasse: {df.iloc[0]['Strasse']}")
print(f"  HausNummer: {df.iloc[0]['HausNummer']}")
print(f"  PLZ: {df.iloc[0]['Plz']}")
print()
print("Record B:")
print(f"  Vorname: {df.iloc[1]['Vorname']}")
print(f"  Name: {df.iloc[1]['Name']}")
print(f"  Name2: {df.iloc[1]['Name2']}")
print(f"  Strasse: {df.iloc[1]['Strasse']}")
print(f"  HausNummer: {df.iloc[1]['HausNummer']}")
print(f"  PLZ: {df.iloc[1]['Plz']}")
print()

# Preprocess
cols = preprocess(df)

print("After preprocessing:")
print(f"  Record A: first='{cols['first'].iloc[0]}', last='{cols['last'].iloc[0]}', name2='{cols['name2'].iloc[0]}'")
print(f"  Record B: first='{cols['first'].iloc[1]}', last='{cols['last'].iloc[1]}', name2='{cols['name2'].iloc[1]}'")
print()

# Score the pair
result = score_pair(0, 1, cols, fuzzy_threshold=0.80, enable_address_aware=True)

print("=" * 70)
print("AFTER FIX:")
print("=" * 70)
if result:
    print(f"  ✓ Match Found!")
    print(f"  Overall Score: {result.score:.1f}%")
    print(f"  Name Score: {result.name_score:.1f}%")
    print(f"  Address Score: {result.addr_score:.1f}%")
    print(f"  Match Type: {result.reason}")
    print(f"  Is Swapped: {result.is_swapped}")
    print()
    print(f"  IMPROVEMENT: {result.score - 77.5:.1f} percentage points!")
else:
    print("  ✗ No match found")

print("=" * 70)
