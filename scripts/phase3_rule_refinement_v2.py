"""
Phase 3: Rule Refinement & Validation (Version 2)

Updated based on improved LLM classifications with Swiss-specific patterns.

New strategy based on LLM findings:
- Cluster 7 (swapped names): Now 0% FP → KEEP (was removed in v1)
- Cluster 3 (fuzzy swapped): Now 0% FP → KEEP (was removed in v1)
- Cluster 5 (gender mismatches): Still 53% FP → Remove or tighten
- Cluster 1 (fuzzy + low sim): Now 27% FP → Apply targeted filters

Actions:
1. Remove ONLY Cluster 5 (gender mismatches with 53% FP)
2. For Cluster 1: Require moderate address match (not just weak)
3. Lower minimum score threshold to 60% (instead of 70%) to keep compound surnames
4. Keep all swapped name patterns (Clusters 3, 7)
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    # Configuration
    input_dir = Path('_bmad-output/analysis/run_20260108_124349')
    clustered_file = input_dir / 'clustered_results.csv'
    llm_labeled_file = input_dir / 'llm_labeled_results.csv'
    output_file = input_dir / 'refined_results_v2.csv'

    print("=" * 80)
    print("PHASE 3: RULE REFINEMENT & VALIDATION (V2)")
    print("=" * 80)
    print("\nStrategy: Keep swapped names & compound surnames, filter gender mismatches")

    # Load data
    print(f"\nLoading data...")
    df = pd.read_csv(clustered_file)
    llm_df = pd.read_csv(llm_labeled_file)

    print(f"Original pairs: {len(df):,}")
    print(f"LLM labeled samples: {len(llm_df)}")

    # Before metrics
    print("\n" + "=" * 80)
    print("BEFORE REFINEMENT")
    print("=" * 80)
    print_metrics(df, "Original")

    # Apply refined actions
    print("\n" + "=" * 80)
    print("APPLYING REFINED ACTIONS")
    print("=" * 80)

    refined_df = df.copy()

    # Action 1: Remove ONLY Cluster 5 (gender mismatches with 53% FP rate)
    print("\n[Action 1] Removing cluster 5 (gender mismatches: 53% FP rate)")
    before_count = len(refined_df)
    refined_df = refined_df[refined_df['cluster'] != 5]
    removed = before_count - len(refined_df)
    print(f"  Removed: {removed:,} pairs ({removed/before_count*100:.1f}%)")
    print(f"  Remaining: {len(refined_df):,} pairs")
    print(f"  Note: Keeping Cluster 7 (swapped names, 0% FP now)")

    # Action 2: For Cluster 1, require moderate or strong address (not weak)
    print("\n[Action 2] Cluster 1: Requiring moderate/strong address match")
    before_count = len(refined_df)

    # Identify Cluster 1 with weak address
    cluster1_weak = (refined_df['cluster'] == 1) & (refined_df['address_ratio_weak'] == True)

    refined_df = refined_df[~cluster1_weak]
    removed = before_count - len(refined_df)
    print(f"  Cluster 1 pairs with weak address: {cluster1_weak.sum():,}")
    print(f"  Removed: {removed:,} pairs")
    print(f"  Remaining: {len(refined_df):,} pairs")

    # Action 3: Apply minimum score threshold of 60% (not 70%)
    print("\n[Action 3] Applying minimum score threshold: 60%")
    print("  (Lowered from 70% to keep compound surnames)")
    before_count = len(refined_df)
    refined_df = refined_df[refined_df['score'] >= 60]
    removed = before_count - len(refined_df)
    print(f"  Removed: {removed:,} pairs ({removed/before_count*100:.1f}%)")
    print(f"  Remaining: {len(refined_df):,} pairs")

    # Action 4: For remaining gender mismatches, require high name similarity
    print("\n[Action 4] Other gender mismatches: Requiring high name similarity")
    before_count = len(refined_df)

    # Identify gender mismatches (not in cluster 5, which is already removed)
    gender_mismatch = refined_df['different_genders_same_address'] == True

    # For gender mismatches, require high name similarity
    gender_violations = gender_mismatch & (
        ~(refined_df['name_similarity_high'])
    )

    refined_df = refined_df[~gender_violations]
    removed = before_count - len(refined_df)
    print(f"  Gender mismatch pairs remaining: {gender_mismatch.sum():,}")
    print(f"  Removed (medium/low similarity): {removed:,} pairs")
    print(f"  Remaining: {len(refined_df):,} pairs")

    # After metrics
    print("\n" + "=" * 80)
    print("AFTER REFINEMENT (V2)")
    print("=" * 80)
    print_metrics(refined_df, "Refined V2")

    # Save refined results
    refined_df.to_csv(output_file, index=False)
    print(f"\nSaved refined results to: {output_file}")

    # Comparison
    print("\n" + "=" * 80)
    print("BEFORE vs AFTER COMPARISON")
    print("=" * 80)

    original_count = len(df)
    refined_count = len(refined_df)
    reduction = original_count - refined_count
    reduction_pct = reduction / original_count * 100

    print(f"\nPairs reduced: {reduction:,} ({reduction_pct:.1f}%)")
    print(f"  Original: {original_count:,}")
    print(f"  Refined:  {refined_count:,}")

    print(f"\nAverage score improvement:")
    print(f"  Original: {df['score'].mean():.2f}%")
    print(f"  Refined:  {refined_df['score'].mean():.2f}%")
    print(f"  Gain:     +{refined_df['score'].mean() - df['score'].mean():.2f}%")

    # Cluster distribution changes
    print(f"\nCluster distribution changes:")
    original_dist = df['cluster'].value_counts().sort_index()
    refined_dist = refined_df['cluster'].value_counts().sort_index()

    for cluster_id in sorted(df['cluster'].unique()):
        original = original_dist.get(cluster_id, 0)
        refined = refined_dist.get(cluster_id, 0)
        change = refined - original
        change_pct = change / original * 100 if original > 0 else 0

        if abs(change_pct) >= 5:  # Show significant changes
            print(f"  Cluster {cluster_id}: {original:,} -> {refined:,} ({change:+,}, {change_pct:+.1f}%)")

    # Validate against LLM labels
    print("\n" + "=" * 80)
    print("VALIDATION AGAINST LLM LABELS (NEW)")
    print("=" * 80)

    validate_refinement(df, refined_df, llm_df)

    print("\n" + "=" * 80)
    print("PHASE 3 V2 COMPLETE!")
    print("=" * 80)
    print(f"\nRefined results saved to: {output_file}")
    print(f"Total pairs reduced by {reduction_pct:.1f}%")
    print(f"Average score improved by +{refined_df['score'].mean() - df['score'].mean():.2f}%")


def print_metrics(df: pd.DataFrame, label: str):
    """Print summary metrics for a dataset."""
    print(f"\n{label} Dataset Metrics:")
    print(f"  Total pairs: {len(df):,}")
    print(f"  Average score: {df['score'].mean():.2f}%")
    print(f"  Median score: {df['score'].median():.2f}%")
    print(f"  Min score: {df['score'].min():.2f}%")
    print(f"  Max score: {df['score'].max():.2f}%")

    # Score distribution
    print(f"\n  Score distribution:")
    print(f"    100%:     {len(df[df['score'] == 100]):,} ({len(df[df['score'] == 100])/len(df)*100:.1f}%)")
    print(f"    90-99%:   {len(df[(df['score'] >= 90) & (df['score'] < 100)]):,} ({len(df[(df['score'] >= 90) & (df['score'] < 100)])/len(df)*100:.1f}%)")
    print(f"    80-89%:   {len(df[(df['score'] >= 80) & (df['score'] < 90)]):,} ({len(df[(df['score'] >= 80) & (df['score'] < 90)])/len(df)*100:.1f}%)")
    print(f"    70-79%:   {len(df[(df['score'] >= 70) & (df['score'] < 80)]):,} ({len(df[(df['score'] >= 70) & (df['score'] < 80)])/len(df)*100:.1f}%)")
    print(f"    60-69%:   {len(df[(df['score'] >= 60) & (df['score'] < 70)]):,} ({len(df[(df['score'] >= 60) & (df['score'] < 70)])/len(df)*100:.1f}%)")
    print(f"    50-59%:   {len(df[(df['score'] >= 50) & (df['score'] < 60)]):,} ({len(df[(df['score'] >= 50) & (df['score'] < 60)])/len(df)*100:.1f}%)")
    print(f"    <50%:     {len(df[df['score'] < 50]):,} ({len(df[df['score'] < 50])/len(df)*100:.1f}%)")

    # Cluster distribution
    print(f"\n  Top 5 clusters:")
    for cluster_id, count in df['cluster'].value_counts().head(5).items():
        print(f"    Cluster {cluster_id}: {count:,} ({count/len(df)*100:.1f}%)")


def validate_refinement(original_df: pd.DataFrame, refined_df: pd.DataFrame, llm_df: pd.DataFrame):
    """Validate refinement using LLM labels."""

    # Create lookup for LLM labels
    llm_lookup = {}
    for idx, row in llm_df.iterrows():
        key = (row['i'], row['j'])
        llm_lookup[key] = row['llm_label']

    # Find which LLM-labeled pairs were removed
    original_pairs = set(zip(original_df['i'], original_df['j']))
    refined_pairs = set(zip(refined_df['i'], refined_df['j']))
    removed_pairs = original_pairs - refined_pairs

    # Analyze removed pairs that were LLM-labeled
    removed_labeled = [pair for pair in removed_pairs if pair in llm_lookup]

    if len(removed_labeled) == 0:
        print("\nNo LLM-labeled pairs were removed (all samples passed refinement filters).")
        return

    # Count how many removed pairs were duplicates vs not duplicates
    removed_duplicates = sum(1 for pair in removed_labeled if llm_lookup[pair] == 'DUPLICATE')
    removed_not_duplicates = sum(1 for pair in removed_labeled if llm_lookup[pair] == 'NOT_DUPLICATE')

    print(f"\nLLM-labeled pairs removed by refinement: {len(removed_labeled)}")
    print(f"  Removed TRUE duplicates (bad removal): {removed_duplicates} ({removed_duplicates/len(removed_labeled)*100:.1f}%)")
    print(f"  Removed FALSE positives (good removal): {removed_not_duplicates} ({removed_not_duplicates/len(removed_labeled)*100:.1f}%)")

    # Estimate impact on false positive rate
    remaining_labeled = [pair for pair in refined_pairs if pair in llm_lookup]
    remaining_not_duplicates = sum(1 for pair in remaining_labeled if llm_lookup[pair] == 'NOT_DUPLICATE')

    if len(remaining_labeled) > 0:
        original_fp_rate = len([p for p in llm_lookup.keys() if llm_lookup[p] == 'NOT_DUPLICATE']) / len(llm_lookup) * 100
        refined_fp_rate = remaining_not_duplicates / len(remaining_labeled) * 100

        print(f"\nEstimated false positive rate (based on LLM samples):")
        print(f"  Original: {original_fp_rate:.1f}%")
        print(f"  Refined:  {refined_fp_rate:.1f}%")
        print(f"  Improvement: {original_fp_rate - refined_fp_rate:.1f} percentage points")

    # Show comparison with V1 results if available
    v1_file = Path('_bmad-output/analysis/run_20260108_124349/refined_results.csv')
    if v1_file.exists():
        v1_df = pd.read_csv(v1_file)
        v1_pairs = set(zip(v1_df['i'], v1_df['j']))
        v1_remaining_labeled = [pair for pair in v1_pairs if pair in llm_lookup]

        print(f"\nComparison with V1 (old prompts + aggressive rules):")
        print(f"  V1 kept: {len(v1_df):,} pairs ({len(v1_remaining_labeled)} LLM-labeled)")
        print(f"  V2 kept: {len(refined_df):,} pairs ({len(remaining_labeled)} LLM-labeled)")
        print(f"  Difference: {len(refined_df) - len(v1_df):,} more pairs kept in V2")

    # Show some examples of removed pairs
    if removed_not_duplicates > 0:
        print(f"\nExamples of FALSE POSITIVES successfully removed:")
        count = 0
        for pair in removed_labeled:
            if llm_lookup[pair] == 'NOT_DUPLICATE' and count < 3:
                # Find the row in llm_df
                row = llm_df[(llm_df['i'] == pair[0]) & (llm_df['j'] == pair[1])].iloc[0]
                print(f"  - Score {row['score']:.0f}%: {row['vorname_i']} {row['name_i']} vs {row['vorname_j']} {row['name_j']}")
                print(f"    Cluster {row['cluster']}, Reason: {row['llm_reasoning'][:80]}...")
                count += 1

    if removed_duplicates > 0:
        print(f"\nExamples of TRUE DUPLICATES incorrectly removed (REVIEW THESE):")
        count = 0
        for pair in removed_labeled:
            if llm_lookup[pair] == 'DUPLICATE' and count < 3:
                # Find the row in llm_df
                row = llm_df[(llm_df['i'] == pair[0]) & (llm_df['j'] == pair[1])].iloc[0]
                print(f"  - Score {row['score']:.0f}%: {row['vorname_i']} {row['name_i']} vs {row['vorname_j']} {row['name_j']}")
                print(f"    Cluster {row['cluster']}, Reason: {row['llm_reasoning'][:80]}...")
                count += 1


if __name__ == '__main__':
    main()
