"""
Phase 3: Rule Refinement & Validation

This script applies evidence-based rule refinements from Phase 2 LLM analysis:
1. Remove worst-performing clusters (5, 7) with 60-67% FP rates
2. Raise minimum score threshold to 70%
3. Strengthen gender-mismatch rules (require exact match + high similarity + DOB)
4. Require DOB or strong address for low name similarity cases

Generates refined results and validates against LLM labels.
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
    output_file = input_dir / 'refined_results.csv'

    print("=" * 80)
    print("PHASE 3: RULE REFINEMENT & VALIDATION")
    print("=" * 80)

    # Load data
    print(f"\nLoading data...")
    df = pd.read_csv(clustered_file)
    llm_df = pd.read_csv(llm_labeled_file)

    print(f"Original pairs: {len(df)}")
    print(f"LLM labeled samples: {len(llm_df)}")

    # Before metrics
    print("\n" + "=" * 80)
    print("BEFORE REFINEMENT")
    print("=" * 80)
    print_metrics(df, "Original")

    # Apply refinement actions
    print("\n" + "=" * 80)
    print("APPLYING REFINEMENT ACTIONS")
    print("=" * 80)

    refined_df = df.copy()

    # Action 1: Remove worst-performing clusters (5, 7)
    print("\n[Action 1] Removing clusters 5 & 7 (high FP rate: 60-67%)")
    before_count = len(refined_df)
    refined_df = refined_df[~refined_df['cluster'].isin([5, 7])]
    removed = before_count - len(refined_df)
    print(f"  Removed: {removed:,} pairs ({removed/before_count*100:.1f}%)")
    print(f"  Remaining: {len(refined_df):,} pairs")

    # Action 2: Raise minimum score threshold to 70%
    print("\n[Action 2] Applying minimum score threshold: 70%")
    before_count = len(refined_df)
    refined_df = refined_df[refined_df['score'] >= 70]
    removed = before_count - len(refined_df)
    print(f"  Removed: {removed:,} pairs ({removed/before_count*100:.1f}%)")
    print(f"  Remaining: {len(refined_df):,} pairs")

    # Action 3: Strengthen gender-mismatch rules
    print("\n[Action 3] Strengthening gender-mismatch rules")
    before_count = len(refined_df)

    # Identify gender mismatches
    gender_mismatch = refined_df['different_genders_same_address'] == True

    # For gender mismatches, require: exact match + high name similarity + exact DOB
    gender_violations = gender_mismatch & (
        ~(
            # Must have exact match (not fuzzy)
            (refined_df['exact_normal'] | refined_df['exact_swapped']) &
            # Must have high name similarity
            (refined_df['name_similarity_high']) &
            # Must have exact DOB
            (refined_df['both_have_exact_dob'])
        )
    )

    refined_df = refined_df[~gender_violations]
    removed = before_count - len(refined_df)
    print(f"  Gender mismatch pairs: {gender_mismatch.sum():,}")
    print(f"  Removed (fuzzy or low similarity): {removed:,} pairs")
    print(f"  Remaining: {len(refined_df):,} pairs")

    # Action 4: Require DOB or strong address for low name similarity
    print("\n[Action 4] Requiring DOB or strong address for low name similarity")
    before_count = len(refined_df)

    # Identify low name similarity pairs
    low_name_sim = refined_df['name_similarity_low'] == True

    # For low name similarity, require: exact DOB OR strong address
    low_sim_violations = low_name_sim & (
        ~(
            # Must have exact DOB, OR
            (refined_df['both_have_exact_dob']) |
            # Must have strong address match
            (refined_df['address_ratio_strong'])
        )
    )

    refined_df = refined_df[~low_sim_violations]
    removed = before_count - len(refined_df)
    print(f"  Low name similarity pairs: {low_name_sim.sum():,}")
    print(f"  Removed (no DOB or strong address): {removed:,} pairs")
    print(f"  Remaining: {len(refined_df):,} pairs")

    # After metrics
    print("\n" + "=" * 80)
    print("AFTER REFINEMENT")
    print("=" * 80)
    print_metrics(refined_df, "Refined")

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

        if change != 0:
            print(f"  Cluster {cluster_id}: {original:,} -> {refined:,} ({change:+,}, {change_pct:+.1f}%)")

    # Validate against LLM labels
    print("\n" + "=" * 80)
    print("VALIDATION AGAINST LLM LABELS")
    print("=" * 80)

    validate_refinement(df, refined_df, llm_df)

    print("\n" + "=" * 80)
    print("PHASE 3 COMPLETE!")
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
