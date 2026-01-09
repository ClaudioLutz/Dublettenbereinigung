"""
Pattern analysis and report generation for entity resolution.

This module provides:
- Disagreement analysis between LLM labels and system scores
- Pattern identification in disagree cases
- Markdown report generation with visualizations
"""

from typing import Dict
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns


def analyze_disagreements(
    llm_labeled: pd.DataFrame,
    system_threshold: float = 75.0
) -> pd.DataFrame:
    """
    Find disagreements between LLM labels and system scores.

    Args:
        llm_labeled: DataFrame with llm_label and score columns
        system_threshold: System score threshold for matches (default: 75.0)

    Returns:
        DataFrame with disagreement analysis by cluster
    """
    print(f"Analyzing disagreements (system threshold: {system_threshold})...")

    # Classify disagreements
    llm_labeled = llm_labeled.copy()
    llm_labeled['system_classification'] = llm_labeled['score'].apply(
        lambda x: 'DUPLICATE' if x >= system_threshold else 'NOT_DUPLICATE'
    )

    llm_labeled['agreement'] = (
        llm_labeled['llm_label'] == llm_labeled['system_classification']
    )

    # Categorize disagreement types
    def categorize_disagreement(row):
        if row['agreement']:
            return 'AGREE'
        elif row['llm_label'] == 'DUPLICATE' and row['system_classification'] == 'NOT_DUPLICATE':
            return 'FALSE_NEGATIVE'  # System missed a match
        else:
            return 'FALSE_POSITIVE'  # System false positive

    llm_labeled['disagreement_type'] = llm_labeled.apply(categorize_disagreement, axis=1)

    # Aggregate by cluster
    cluster_analysis = llm_labeled.groupby('cluster').agg({
        'agreement': ['sum', 'count', 'mean'],
        'disagreement_type': lambda x: x.value_counts().to_dict()
    }).reset_index()

    cluster_analysis.columns = ['cluster', 'agreements', 'total', 'agreement_rate', 'disagreement_breakdown']

    print(f"\nDisagreement Summary:")
    print(f"  Total pairs: {len(llm_labeled)}")
    print(f"  Agreements: {llm_labeled['agreement'].sum()} ({llm_labeled['agreement'].mean()*100:.1f}%)")
    print(f"  False Negatives: {(llm_labeled['disagreement_type'] == 'FALSE_NEGATIVE').sum()}")
    print(f"  False Positives: {(llm_labeled['disagreement_type'] == 'FALSE_POSITIVE').sum()}")

    return cluster_analysis


def identify_rule_patterns(
    llm_labeled: pd.DataFrame,
    rule_features: pd.DataFrame
) -> Dict:
    """
    Identify patterns in disagreement cases.

    Args:
        llm_labeled: DataFrame with LLM labels and disagreement info
        rule_features: DataFrame with boolean rule features

    Returns:
        Dictionary with pattern insights
    """
    print("Identifying rule patterns in disagreements...")

    # Filter to disagreement cases
    disagreements = llm_labeled[llm_labeled['agreement'] == False].copy()

    if len(disagreements) == 0:
        print("  No disagreements found!")
        return {
            'total_disagreements': 0,
            'patterns': []
        }

    # Get feature columns
    feature_cols = [col for col in rule_features.columns
                   if any(col.startswith(prefix) for prefix in
                   ['exact_', 'fuzzy_', 'address_', 'phonetic_', 'gate_', 'both_', 'one_', 'name_', 'first_', 'last_', 'different_'])]

    patterns = []
    for feature in feature_cols:
        if feature in disagreements.columns:
            # Calculate correlation between feature and disagreement
            feature_prevalence_disagreement = disagreements[feature].mean()
            feature_prevalence_overall = llm_labeled[feature].mean()

            if feature_prevalence_disagreement > feature_prevalence_overall * 1.5:
                # This feature is over-represented in disagreements
                patterns.append({
                    'feature': feature,
                    'disagreement_rate': feature_prevalence_disagreement,
                    'overall_rate': feature_prevalence_overall,
                    'lift': feature_prevalence_disagreement / (feature_prevalence_overall + 0.001)
                })

    # Sort by lift
    patterns = sorted(patterns, key=lambda x: x['lift'], reverse=True)[:10]

    print(f"  Found {len(patterns)} patterns with elevated disagreement rates")

    return {
        'total_disagreements': len(disagreements),
        'disagreement_rate': len(disagreements) / len(llm_labeled),
        'patterns': patterns
    }


def generate_pattern_report(
    analysis_results: Dict,
    output_path: str
) -> None:
    """
    Generate markdown pattern report.

    Args:
        analysis_results: Dictionary with analysis results from previous steps
        output_path: Path to save markdown report
    """
    print(f"Generating pattern report: {output_path}")

    report_lines = []

    # Header
    report_lines.append("# Pattern Discovery Analysis Report")
    report_lines.append("")
    report_lines.append(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")

    # Executive Summary
    report_lines.append("## Executive Summary")
    report_lines.append("")
    total_pairs = analysis_results.get('total_pairs', 0)
    disagreement_rate = analysis_results.get('disagreement_rate', 0) * 100
    report_lines.append(f"- **Total pairs analyzed:** {total_pairs}")
    report_lines.append(f"- **LLM-System disagreement rate:** {disagreement_rate:.1f}%")
    report_lines.append("")

    # Top Recommendations
    report_lines.append("## Top Recommendations")
    report_lines.append("")
    patterns = analysis_results.get('patterns', [])
    if patterns:
        for i, pattern in enumerate(patterns[:5], 1):
            feature = pattern['feature']
            lift = pattern['lift']
            report_lines.append(f"{i}. **{feature}**: {lift:.2f}x more common in disagreements")
    else:
        report_lines.append("No significant patterns identified.")
    report_lines.append("")

    # Cluster Analysis
    report_lines.append("## Cluster-by-Cluster Analysis")
    report_lines.append("")
    cluster_data = analysis_results.get('cluster_analysis', pd.DataFrame())
    if not cluster_data.empty:
        report_lines.append("| Cluster | Total | Agreements | Agreement Rate |")
        report_lines.append("|---------|-------|------------|----------------|")
        for _, row in cluster_data.iterrows():
            cluster = row['cluster']
            total = row['total']
            agreements = row['agreements']
            rate = row['agreement_rate'] * 100
            report_lines.append(f"| {cluster} | {total} | {agreements} | {rate:.1f}% |")
    report_lines.append("")

    # Pattern Details
    report_lines.append("## Pattern Details")
    report_lines.append("")
    if patterns:
        report_lines.append("| Feature | Disagreement Rate | Overall Rate | Lift |")
        report_lines.append("|---------|-------------------|--------------|------|")
        for pattern in patterns:
            feature = pattern['feature']
            dis_rate = pattern['disagreement_rate'] * 100
            overall_rate = pattern['overall_rate'] * 100
            lift = pattern['lift']
            report_lines.append(f"| {feature} | {dis_rate:.1f}% | {overall_rate:.1f}% | {lift:.2f}x |")
    report_lines.append("")

    # Write report
    with open(output_path, 'w') as f:
        f.write('\n'.join(report_lines))

    print(f"Report saved: {output_path}")
