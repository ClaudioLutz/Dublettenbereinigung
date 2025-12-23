import pandas as pd

# Load the cluster mapping
df = pd.read_csv('output_splink/clusters/cluster_mapping.csv')

print("=" * 60)
print("DUPLICATE DETECTION RESULTS")
print("=" * 60)
print(f"\nTotal records processed: {len(df):,}")
print(f"Total unique clusters: {df['cluster_id'].nunique():,}")

# Find records that have duplicates (cluster_id appears more than once)
duplicated_mask = df.duplicated('cluster_id', keep=False)
duplicates_df = df[duplicated_mask]

print(f"Records that are part of duplicate clusters: {len(duplicates_df):,}")
print(f"Number of duplicate clusters: {duplicates_df['cluster_id'].nunique():,}")

if len(duplicates_df) > 0:
    print("\n" + "=" * 60)
    print("SAMPLE OF DUPLICATE CLUSTERS (first 5 clusters)")
    print("=" * 60)
    
    # Show first few duplicate clusters
    sample_clusters = duplicates_df['cluster_id'].unique()[:5]
    for cluster_id in sample_clusters:
        cluster_records = df[df['cluster_id'] == cluster_id]
        print(f"\n--- Cluster {cluster_id} ({len(cluster_records)} records) ---")
        print(cluster_records[['unique_id', 'cluster_id']])

print("\n" + "=" * 60)
print(f"\nFull results saved in: output_splink/clusters/cluster_mapping.csv")
print(f"Each row shows: unique_id and cluster_id")
print(f"Records with the same cluster_id are duplicates!")
print("=" * 60)
