"""
Phase 2: LLM Calibration - Label sampled pairs using DeepSeek.

This script:
1. Loads the sampled pairs from Phase 1
2. Uses DeepSeek API to label each pair as DUPLICATE or NOT_DUPLICATE
3. Analyzes false positive rates by cluster
4. Generates recommendations for rule improvements
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dedupe.analysis.llm_labeling import DeepSeekClient


def main():
    # Configuration
    input_dir = Path('_bmad-output/analysis/run_20260108_124349')
    sampled_file = input_dir / 'sampled_for_labeling.csv'
    output_file = input_dir / 'llm_labeled_results.csv'

    print("=" * 80)
    print("PHASE 2: LLM CALIBRATION")
    print("=" * 80)

    # Load sampled pairs
    print(f"\nLoading sampled pairs from: {sampled_file}")
    df = pd.read_csv(sampled_file)
    print(f"Total sampled pairs: {len(df)}")
    print(f"Clusters represented: {df['cluster'].nunique()}")

    # Initialize DeepSeek client
    print("\nInitializing DeepSeek client...")
    try:
        client = DeepSeekClient(max_cost=1.0)  # $1 budget for ~174 pairs
        print(f"Model: {client.model}")
        print(f"Cost ceiling: ${client.max_cost:.2f}")
    except ValueError as e:
        print(f"ERROR: {e}")
        print("\nPlease ensure DEEPSEEK_API_KEY is set in your .env file.")
        sys.exit(1)

    # Label pairs
    print("\n" + "=" * 80)
    print("LABELING PAIRS WITH DEEPSEEK")
    print("=" * 80)

    labeled_df, low_conf_indices = client.label_batch(
        df,
        confidence_threshold=0.85
    )

    # Save results
    labeled_df.to_csv(output_file, index=False)
    print(f"\nSaved labeled results to: {output_file}")

    # Analyze results by cluster
    print("\n" + "=" * 80)
    print("CLUSTER ANALYSIS")
    print("=" * 80)

    analyze_results(labeled_df)

    # Generate recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    generate_recommendations(labeled_df)

    print("\n" + "=" * 80)
    print("PHASE 2 COMPLETE!")
    print("=" * 80)
    print(f"\nTotal cost: ${client.total_cost:.4f}")
    print(f"Output file: {output_file}")


def analyze_results(df: pd.DataFrame):
    """Analyze false positive rates by cluster."""

    # Group by cluster
    for cluster_id in sorted(df['cluster'].unique()):
        cluster_df = df[df['cluster'] == cluster_id]

        # Calculate metrics
        total = len(cluster_df)
        duplicates = len(cluster_df[cluster_df['llm_label'] == 'DUPLICATE'])
        not_duplicates = len(cluster_df[cluster_df['llm_label'] == 'NOT_DUPLICATE'])
        errors = len(cluster_df[cluster_df['llm_label'] == 'ERROR'])

        duplicate_rate = duplicates / total * 100 if total > 0 else 0
        false_positive_rate = not_duplicates / total * 100 if total > 0 else 0

        avg_score = cluster_df['score'].mean()
        avg_confidence = cluster_df[cluster_df['llm_label'] != 'ERROR']['llm_confidence'].mean()

        print(f"\nCluster {cluster_id} ({total} samples):")
        print(f"  Avg rule score: {avg_score:.1f}%")
        print(f"  Duplicates: {duplicates} ({duplicate_rate:.1f}%)")
        print(f"  NOT duplicates: {not_duplicates} ({false_positive_rate:.1f}%)")
        if errors > 0:
            print(f"  Errors: {errors}")
        print(f"  Avg LLM confidence: {avg_confidence:.2f}")

        # Show a few examples of false positives
        if not_duplicates > 0:
            false_positives = cluster_df[cluster_df['llm_label'] == 'NOT_DUPLICATE']
            print(f"  Example false positives:")
            for idx, row in false_positives.head(2).iterrows():
                print(f"    - Score {row['score']:.0f}%: {row['vorname_i']} {row['name_i']} vs {row['vorname_j']} {row['name_j']}")
                print(f"      Reason: {row['llm_reasoning'][:100]}...")


def generate_recommendations(df: pd.DataFrame):
    """Generate recommendations for rule improvements."""

    # Identify high false positive clusters
    cluster_stats = []
    for cluster_id in sorted(df['cluster'].unique()):
        cluster_df = df[df['cluster'] == cluster_id]
        total = len(cluster_df)
        not_duplicates = len(cluster_df[cluster_df['llm_label'] == 'NOT_DUPLICATE'])
        false_positive_rate = not_duplicates / total if total > 0 else 0

        cluster_stats.append({
            'cluster_id': cluster_id,
            'total_pairs': total,
            'false_positive_rate': false_positive_rate,
            'avg_score': cluster_df['score'].mean()
        })

    stats_df = pd.DataFrame(cluster_stats).sort_values('false_positive_rate', ascending=False)

    print("\nTop False Positive Clusters:")
    for idx, row in stats_df.head(5).iterrows():
        print(f"  Cluster {row['cluster_id']}: {row['false_positive_rate']*100:.1f}% FP rate "
              f"(avg score {row['avg_score']:.1f}%, {row['total_pairs']} samples)")

    print("\nRecommended Actions:")

    # High FP rate clusters
    high_fp_clusters = stats_df[stats_df['false_positive_rate'] > 0.3]['cluster_id'].tolist()
    if high_fp_clusters:
        print(f"\n1. INVESTIGATE HIGH FALSE POSITIVE CLUSTERS: {high_fp_clusters}")
        print(f"   These clusters have >30% false positive rates.")
        print(f"   Action: Review cluster profiles and adjust business rules.")

    # Gender mismatch cluster (likely cluster 5)
    gender_clusters = df[df['cluster'] == 5]
    if len(gender_clusters) > 0:
        not_dup_rate = len(gender_clusters[gender_clusters['llm_label'] == 'NOT_DUPLICATE']) / len(gender_clusters)
        if not_dup_rate > 0.5:
            print(f"\n2. GENDER MISMATCH RULE VALIDATION:")
            print(f"   Cluster 5 (gender mismatches) has {not_dup_rate*100:.1f}% NOT_DUPLICATE rate.")
            print(f"   Action: Consider strengthening the gender-based filtering rule.")

    # Low score clusters
    low_score_clusters = stats_df[(stats_df['avg_score'] < 70) & (stats_df['false_positive_rate'] > 0.2)]
    if len(low_score_clusters) > 0:
        print(f"\n3. LOW CONFIDENCE CLUSTERS:")
        for idx, row in low_score_clusters.iterrows():
            print(f"   Cluster {row['cluster_id']}: avg score {row['avg_score']:.1f}%, FP rate {row['false_positive_rate']*100:.1f}%")
        print(f"   Action: Consider raising minimum score threshold or filtering these patterns.")

    # Overall statistics
    total_not_dup = len(df[df['llm_label'] == 'NOT_DUPLICATE'])
    overall_fp_rate = total_not_dup / len(df) * 100
    print(f"\n4. OVERALL FALSE POSITIVE RATE: {overall_fp_rate:.1f}%")
    if overall_fp_rate > 20:
        print(f"   High overall FP rate suggests rules need tightening.")
    elif overall_fp_rate < 10:
        print(f"   Low overall FP rate suggests rules are working well.")
    else:
        print(f"   Moderate FP rate is acceptable for initial review queue.")


if __name__ == '__main__':
    main()
