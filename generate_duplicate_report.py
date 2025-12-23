"""
Generate a readable duplicate report with names, addresses, etc.
This joins the cluster mapping with the original data to show actual duplicate records.
"""
import pandas as pd
import sys
from pathlib import Path

def generate_duplicate_report(cache_dir="cache_splink", 
                              cluster_file="output_splink/clusters/cluster_mapping.csv",
                              output_file="duplicate_report.csv",
                              output_excel="duplicate_report.xlsx"):
    """
    Generate a detailed duplicate report showing names, addresses for all duplicate records.
    """
    
    print("=" * 80)
    print("GENERATING DUPLICATE REPORT WITH NAMES AND ADDRESSES")
    print("=" * 80)
    
    # 1. Load cluster mapping
    print("\n1. Loading cluster mapping...")
    try:
        cluster_df = pd.read_csv(cluster_file)
        print(f"   ✓ Loaded {len(cluster_df):,} records from cluster mapping")
    except FileNotFoundError:
        print(f"   ✗ ERROR: {cluster_file} not found!")
        print("   Run the splink pipeline first: python scripts\\run_splink_end2end.py --use-data-py")
        sys.exit(1)
    
    # 2. Load original data from parquet cache (has all the names, addresses, etc.)
    print("\n2. Loading original data with names and addresses...")
    cache_path = Path(cache_dir)
    parquet_files = list(cache_path.glob("shard=*/part-*.parquet"))
    
    if not parquet_files:
        print(f"   ✗ ERROR: No parquet files found in {cache_dir}")
        sys.exit(1)
    
    print(f"   Found {len(parquet_files)} parquet files")
    
    # Read all parquet files
    dfs = []
    for pf in parquet_files:
        df_chunk = pd.read_parquet(pf)
        dfs.append(df_chunk)
    
    original_data = pd.concat(dfs, ignore_index=True)
    print(f"   ✓ Loaded {len(original_data):,} records with full data")
    
    # 3. Join cluster mapping with original data
    print("\n3. Joining cluster IDs with original data...")
    merged = original_data.merge(cluster_df, on='unique_id', how='inner')
    print(f"   ✓ Merged {len(merged):,} records")
    
    # 4. Find duplicates (records where cluster_id appears more than once)
    print("\n4. Finding duplicate records...")
    cluster_counts = merged['cluster_id'].value_counts()
    duplicate_clusters = cluster_counts[cluster_counts > 1].index
    
    duplicates = merged[merged['cluster_id'].isin(duplicate_clusters)].copy()
    duplicates = duplicates.sort_values(['cluster_id', 'unique_id'])
    
    print(f"   ✓ Found {len(duplicates):,} records in duplicate clusters")
    print(f"   ✓ Number of duplicate clusters: {len(duplicate_clusters):,}")
    
    # 5. Select relevant columns for the report
    print("\n5. Preparing duplicate report...")
    
    # Select columns to include in report (adjust as needed)
    report_columns = [
        'cluster_id',
        'unique_id', 
        'Name', 
        'Vorname', 
        'Name2',
        'Strasse', 
        'HausNummer', 
        'Plz', 
        'Ort',
        'Geburtstag',
        'Jahrgang',
        'Crefo',
        'Quelle_95',
        'Erfasst'
    ]
    
    # Only include columns that exist
    available_columns = [col for col in report_columns if col in duplicates.columns]
    duplicates_report = duplicates[available_columns]
    
    # Add a count column showing how many records in each cluster
    cluster_size = duplicates.groupby('cluster_id').size().rename('records_in_cluster')
    duplicates_report = duplicates_report.merge(cluster_size, left_on='cluster_id', right_index=True)
    
    # Reorder so cluster size is second column
    cols = duplicates_report.columns.tolist()
    cols.remove('records_in_cluster')
    cols.insert(1, 'records_in_cluster')
    duplicates_report = duplicates_report[cols]
    
    # 6. Save to CSV and Excel
    print("\n6. Saving report files...")
    duplicates_report.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"   ✓ CSV saved: {output_file}")
    
    try:
        duplicates_report.to_excel(output_excel, index=False, engine='openpyxl')
        print(f"   ✓ Excel saved: {output_excel}")
    except Exception as e:
        print(f"   ⚠ Could not save Excel file: {e}")
        print(f"   (Install openpyxl: pip install openpyxl)")
    
    # 7. Show summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Total records processed:          {len(original_data):,}")
    print(f"Records with duplicates:          {len(duplicates):,}")
    print(f"Number of duplicate clusters:     {len(duplicate_clusters):,}")
    print(f"Largest cluster size:             {cluster_counts.max()}")
    print(f"Average cluster size (dupes):     {cluster_counts[duplicate_clusters].mean():.2f}")
    
    # 8. Show sample of duplicates
    print("\n" + "=" * 80)
    print("SAMPLE OF DUPLICATE CLUSTERS (first 3 clusters)")
    print("=" * 80)
    
    for i, cluster_id in enumerate(list(duplicate_clusters)[:3]):
        cluster_records = duplicates_report[duplicates_report['cluster_id'] == cluster_id]
        print(f"\n--- Cluster {cluster_id} ({len(cluster_records)} records) ---")
        
        # Show key fields for each record in cluster
        for idx, row in cluster_records.iterrows():
            print(f"  Record {row['unique_id']}: {row.get('Name', 'N/A')} {row.get('Vorname', 'N/A')}, "
                  f"{row.get('Strasse', 'N/A')} {row.get('HausNummer', 'N/A')}, "
                  f"{row.get('Plz', 'N/A')} {row.get('Ort', 'N/A')}")
    
    print("\n" + "=" * 80)
    print(f"FULL REPORT SAVED TO: {output_file}")
    print("=" * 80)
    
    return duplicates_report

if __name__ == "__main__":
    generate_duplicate_report()
