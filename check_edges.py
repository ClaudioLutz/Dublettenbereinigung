import pandas as pd
import glob

# Check edges files
edge_files = glob.glob('output_splink/edges/*.parquet')
print(f"Total edge files: {len(edge_files)}")

total_matches = 0
for f in edge_files[:10]:  # Check first 10
    try:
        df = pd.read_parquet(f)
        if len(df) > 0:
            print(f"{f}: {len(df)} matches")
            print(f"  Columns: {list(df.columns)}")
            print(f"  Sample:\n{df.head(2)}\n")
        total_matches += len(df)
    except Exception as e:
        print(f"{f}: Error - {e}")

print(f"\nTotal matches found in first 10 shards: {total_matches}")

# Check cluster file
try:
    cluster_df = pd.read_csv('output_splink/clusters/cluster_mapping.csv')
    print(f"\nCluster mapping records: {len(cluster_df)}")
except Exception as e:
    print(f"\nCluster mapping error: {e}")
