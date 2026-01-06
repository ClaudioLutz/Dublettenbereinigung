"""Analyze ML deduplication results - find highest confidence duplicates."""
import pandas as pd

print('Finding TOP matches by confidence...')
print()

# Collect matches above 50%
top_matches = []
total_scanned = 0

for chunk in pd.read_csv('results_ml.csv', chunksize=2000000, low_memory=False):
    total_scanned += len(chunk)
    matches = chunk[chunk['confidence'] > 50]
    if len(matches) > 0:
        top_matches.append(matches)
    print(f'Scanned {total_scanned:,} rows...', end='\r')

print()
print()

if top_matches:
    df = pd.concat(top_matches).sort_values('confidence', ascending=False)
    unique_pairs = len(df['match_id'].unique())

    print(f'=== MATCHES WITH CONFIDENCE > 50%: {unique_pairs} pairs ===')
    print()

    # Show top 15 pairs
    seen = set()
    count = 0
    for match_id in df['match_id'].values:
        if match_id in seen:
            continue
        seen.add(match_id)

        pair = df[df['match_id'] == match_id]
        conf = pair['confidence'].iloc[0]

        print(f'=== Match (Confidence: {conf:.1f}%) ===')
        for _, row in pair.iterrows():
            print(f"  [{row['position']}] {row['vorname']} {row['name']}")
            print(f"      Address: {row['strasse']} {row['hausnummer']}, {row['plz']} {row['ort']}")
            print(f"      Crefo: {row['crefo']}")
        print()

        count += 1
        if count >= 15:
            break

    # Distribution
    print('=== CONFIDENCE DISTRIBUTION (>50%) ===')
    print(f"  50-55%: {len(df[(df['confidence'] > 50) & (df['confidence'] <= 55)]) // 2} pairs")
    print(f"  55-60%: {len(df[(df['confidence'] > 55) & (df['confidence'] <= 60)]) // 2} pairs")
    print(f"  60-65%: {len(df[df['confidence'] > 60]) // 2} pairs")
else:
    print('No matches above 50% confidence found')

    # Show what we have
    sample = pd.read_csv('results_ml.csv', nrows=1000000, low_memory=False)
    print(f"Max confidence: {sample['confidence'].max():.1f}%")

    # Show some 40%+ matches
    top = sample[sample['confidence'] > 40].sort_values('confidence', ascending=False)
    if len(top) > 0:
        print(f"\nShowing matches > 40% ({len(top)//2} pairs in sample):")
        seen = set()
        for match_id in top['match_id'].values[:20]:
            if match_id in seen:
                continue
            seen.add(match_id)
            pair = top[top['match_id'] == match_id]
            conf = pair['confidence'].iloc[0]
            print(f"\n=== Match (Confidence: {conf:.1f}%) ===")
            for _, row in pair.iterrows():
                print(f"  [{row['position']}] {row['vorname']} {row['name']}")
                print(f"      {row['strasse']} {row['hausnummer']}, {row['plz']} {row['ort']}")
