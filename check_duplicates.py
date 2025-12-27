"""Check for duplicate rows in the output CSV"""
import pandas as pd

# Read the CSV
df = pd.read_csv('modular_results.csv')

print(f"Total rows: {len(df)}")
print(f"Unique rows: {len(df.drop_duplicates())}")
print(f"Duplicate rows: {len(df) - len(df.drop_duplicates())}")

# Check for duplicate match_ids
match_ids = df['match_id'].unique()
print(f"\nUnique match_ids: {len(match_ids)}")
print(f"Total match_id entries: {len(df)}")

# Since each match has 2 rows (A and B), we expect:
# Unique matches = Total rows / 2
expected_unique = len(df) // 2
actual_unique = len(match_ids)

print(f"\nExpected unique matches: {expected_unique}")
print(f"Actual unique matches: {actual_unique}")

if expected_unique == actual_unique:
    print("\n✅ NO DUPLICATES - Each match appears exactly once (2 rows per match)")
else:
    print(f"\n❌ DUPLICATES FOUND - {actual_unique - expected_unique} extra matches")
    # Show duplicates
    dup_ids = df[df.duplicated(subset=['match_id', 'position'], keep=False)]['match_id'].unique()
    if len(dup_ids) > 0:
        print(f"\nDuplicate match_ids: {dup_ids[:5]}")  # Show first 5
