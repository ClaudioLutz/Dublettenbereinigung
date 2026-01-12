"""
Generate tiered output files from clustered results (Story 1.1, 1.2).

This script reads clustered results with LLM validation labels and generates:
- Tier 1 (auto_merge_pairs.csv): Pairs from clusters with 0% false positive rate
- Tier 2 (review_queue_pairs.csv): Pairs from clusters with >0% false positive rate

Supports two modes:
1. FP-rate based classification (original Story 1.1)
2. YAML configuration-based classification (Story 1.2)

Usage:
    python scripts/generate_tiered_output.py --input-dir PATH
    python scripts/generate_tiered_output.py --input-dir PATH --config config/cluster_labels_v1.yaml

Arguments:
    --input-dir: Directory containing clustered_results.csv and llm_labeled_results.csv
    --config: Optional YAML config file with cluster-to-tier mappings

Exit Codes:
    0: Success
    1: Error (file not found, missing columns, validation failure)
"""

import sys
import time
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
import pandas as pd
import argparse
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Valid cluster range per AC5
VALID_CLUSTER_MIN = 0
VALID_CLUSTER_MAX = 14


def calculate_cluster_fp_rates(df: pd.DataFrame) -> Dict[int, float]:
    """
    Calculate false positive rate per cluster.

    Args:
        df: DataFrame with 'cluster' and 'llm_label' columns

    Returns:
        Dictionary mapping cluster ID -> FP rate percentage (0.0-100.0)

    Example:
        {0: 15.2, 1: 8.7, 3: 0.0, 4: 0.0, ...}
    """
    if df.empty:
        return {}

    fp_rates = {}

    for cluster_id in sorted(df['cluster'].unique()):
        cluster_df = df[df['cluster'] == cluster_id]
        total = len(cluster_df)

        if total == 0:
            continue

        # Count NOT_DUPLICATE labels (false positives)
        not_duplicates = len(cluster_df[cluster_df['llm_label'] == 'NOT_DUPLICATE'])

        # Calculate FP rate as percentage
        fp_rate = (not_duplicates / total) * 100.0
        fp_rates[cluster_id] = fp_rate

    return fp_rates


def classify_tiers(
    df: pd.DataFrame,
    fp_rates: Dict[int, float],
    tier1_threshold: float = 0.0
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Classify pairs into Tier 1 (auto-merge) and Tier 2 (review).

    Args:
        df: Full DataFrame with cluster assignments
        fp_rates: Cluster FP rates from calculate_cluster_fp_rates()
        tier1_threshold: Maximum FP% for Tier 1 (default: 0.0)

    Returns:
        Tuple of (tier1_df, tier2_df)
    """
    # Identify clusters eligible for Tier 1 (FP rate <= threshold)
    tier1_clusters = {
        cluster_id
        for cluster_id, fp_rate in fp_rates.items()
        if fp_rate <= tier1_threshold
    }

    # Split DataFrame by tier
    tier1_df = df[df['cluster'].isin(tier1_clusters)].copy()
    tier2_df = df[~df['cluster'].isin(tier1_clusters)].copy()

    return tier1_df, tier2_df


def validate_cluster_range(df: pd.DataFrame, min_cluster: int = VALID_CLUSTER_MIN, max_cluster: int = VALID_CLUSTER_MAX) -> None:
    """
    Validate all cluster assignments are within valid range (AC5).

    Args:
        df: DataFrame with 'cluster' column
        min_cluster: Minimum valid cluster ID (default: 0)
        max_cluster: Maximum valid cluster ID (default: 14)

    Raises:
        ValueError: If any cluster values are outside valid range
    """
    cluster_values = df['cluster'].unique()
    invalid_clusters = [c for c in cluster_values if c < min_cluster or c > max_cluster]

    if invalid_clusters:
        raise ValueError(
            f"Invalid cluster values found: {invalid_clusters}. "
            f"Valid range is {min_cluster}-{max_cluster}."
        )


def validate_tier_integrity(
    original_df: pd.DataFrame,
    tier1_df: pd.DataFrame,
    tier2_df: pd.DataFrame
) -> None:
    """
    Validate no data loss or duplication across tiers.

    Args:
        original_df: Original input DataFrame
        tier1_df: Tier 1 (auto-merge) DataFrame
        tier2_df: Tier 2 (review queue) DataFrame

    Raises:
        AssertionError: If validation fails
    """
    # Check no overlap between tiers FIRST (before count check)
    tier1_ids = set(zip(tier1_df['i'], tier1_df['j']))
    tier2_ids = set(zip(tier2_df['i'], tier2_df['j']))
    overlap = tier1_ids & tier2_ids
    assert len(overlap) == 0, f"Duplicate pairs found across tiers: {len(overlap)}"

    # Check total count
    original_count = len(original_df)
    tier_total = len(tier1_df) + len(tier2_df)
    assert tier_total == original_count, \
        f"Data loss detected: {original_count} input pairs -> {tier_total} output pairs"

    # Check all pairs accounted for
    original_ids = set(zip(original_df['i'], original_df['j']))
    output_ids = tier1_ids | tier2_ids
    assert original_ids == output_ids, "Pair ID mismatch between input and output"


def save_with_bom(df: pd.DataFrame, path: Path) -> None:
    """
    Save DataFrame to CSV with UTF-8 BOM encoding (Excel compatible).

    Args:
        df: DataFrame to save
        path: Output file path
    """
    df.to_csv(path, index=False, encoding='utf-8-sig')  # utf-8-sig adds BOM
    print(f"[OK] Saved {len(df):,} rows to: {path}")


def wide_to_stacked(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert wide format (one row per pair with _i/_j suffixes) to stacked format
    (two rows per pair with A/B positions).

    Args:
        df: DataFrame in wide format with columns like vorname_i, vorname_j, etc.

    Returns:
        DataFrame in stacked format with position column (A/B) and single set of fields
    """
    if df.empty:
        return df

    # Identify columns for each record type
    cols_i = [c for c in df.columns if c.endswith('_i')]
    cols_j = [c for c in df.columns if c.endswith('_j')]

    # Common columns (not record-specific)
    record_specific = set(cols_i + cols_j + ['i', 'j'])
    common_cols = [c for c in df.columns if c not in record_specific]

    # Build record A rows (from _i columns)
    rows_a = df[common_cols].copy()
    rows_a['position'] = 'A'
    rows_a['index'] = df['i']
    for col in cols_i:
        base_name = col[:-2]  # remove _i suffix
        rows_a[base_name] = df[col]

    # Build record B rows (from _j columns)
    rows_b = df[common_cols].copy()
    rows_b['position'] = 'B'
    rows_b['index'] = df['j']
    for col in cols_j:
        base_name = col[:-2]  # remove _j suffix
        rows_b[base_name] = df[col]

    # Stack A and B rows together
    stacked = pd.concat([rows_a, rows_b], ignore_index=True)
    stacked = stacked.sort_values(['match_id', 'position']).reset_index(drop=True)

    # Reorder columns: match_id, position, index first, then common, then record fields
    priority_cols = ['match_id', 'position', 'index', 'cluster', 'confidence', 'reason']
    priority_cols = [c for c in priority_cols if c in stacked.columns]
    other_cols = [c for c in stacked.columns if c not in priority_cols]
    stacked = stacked[priority_cols + other_cols]

    return stacked


def reorder_columns_for_ac4(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reorder DataFrame columns to match AC4 specification.

    AC4 specifies: match_id, cluster, confidence, i, j, and all original record fields

    Args:
        df: DataFrame with match_id, cluster, confidence columns

    Returns:
        DataFrame with columns reordered per AC4
    """
    # Define priority columns in AC4 order
    priority_cols = ['match_id', 'cluster', 'confidence', 'i', 'j']

    # Get remaining columns in original order
    other_cols = [c for c in df.columns if c not in priority_cols]

    # Reorder
    return df[priority_cols + other_cols]


def load_clustered_results(
    clustered_path: Path,
    llm_labeled_path: Path
) -> Tuple[pd.DataFrame, Dict[int, float]]:
    """
    Load and merge clustered results with LLM labels.

    Args:
        clustered_path: Path to clustered_results.csv
        llm_labeled_path: Path to llm_labeled_results.csv

    Returns:
        Tuple of (clustered_df, fp_rates) where:
        - clustered_df: DataFrame with all pairs and cluster assignments
        - fp_rates: Dictionary mapping cluster ID -> FP rate percentage

    Raises:
        ValueError: If required columns are missing or cluster values invalid
        FileNotFoundError: If input files don't exist
    """
    # Validate files exist
    if not clustered_path.exists():
        raise FileNotFoundError(f"File not found: {clustered_path}")
    if not llm_labeled_path.exists():
        raise FileNotFoundError(f"File not found: {llm_labeled_path}")

    # Load clustered results
    print(f"Loading clustered results from: {clustered_path}")
    clustered_df = pd.read_csv(clustered_path)
    print(f"  Total pairs: {len(clustered_df):,}")

    # Check for and remove duplicate (i,j) pairs
    original_count = len(clustered_df)
    clustered_df = clustered_df.drop_duplicates(subset=['i', 'j'], keep='first')
    if len(clustered_df) < original_count:
        print(f"  WARNING: Removed {original_count - len(clustered_df):,} duplicate pairs")
        print(f"  Unique pairs: {len(clustered_df):,}")

    # Validate required columns in clustered results
    required_cols = ['i', 'j', 'score', 'cluster']
    missing = [col for col in required_cols if col not in clustered_df.columns]
    if missing:
        raise ValueError(f"Missing required columns in {clustered_path}: {missing}")

    # Validate cluster range (AC5)
    validate_cluster_range(clustered_df)
    print(f"  [OK] Cluster values validated (range {VALID_CLUSTER_MIN}-{VALID_CLUSTER_MAX})")

    # Load LLM labeled results
    print(f"Loading LLM labels from: {llm_labeled_path}")
    llm_df = pd.read_csv(llm_labeled_path)
    print(f"  Labeled pairs: {len(llm_df):,}")

    # Validate required columns in LLM results
    llm_required = ['i', 'j', 'cluster', 'llm_label']
    missing_llm = [col for col in llm_required if col not in llm_df.columns]
    if missing_llm:
        raise ValueError(f"Missing required columns in {llm_labeled_path}: {missing_llm}")

    # Create cluster -> FP rate mapping from LLM validation
    print("\nCalculating FP rates per cluster from LLM validation...")
    fp_rates = calculate_cluster_fp_rates(llm_df)

    # Display FP rates
    print("\nCluster FP Rates (from LLM validation):")
    for cluster_id in sorted(fp_rates.keys()):
        tier = "Tier 1 (Auto-Merge)" if fp_rates[cluster_id] == 0.0 else "Tier 2 (Review)"
        print(f"  Cluster {cluster_id:2d}: {fp_rates[cluster_id]:5.1f}% FP -> {tier}")

    # Return clustered_df with fp_rates for tier classification
    return clustered_df, fp_rates


def load_cluster_tier_mapping(
    config_path: Path,
    default_tier: int = 2,
    num_clusters: int = 15
) -> Dict[int, int]:
    """
    Load cluster-to-tier mapping from YAML configuration (Story 1.2).

    Args:
        config_path: Path to cluster_labels_v1.yaml
        default_tier: Default tier for unmapped clusters (default: 2 - safe fallback)
        num_clusters: Expected number of clusters (default: 15, i.e., 0-14)

    Returns:
        Dictionary mapping cluster ID (0-14) -> tier (1 or 2)

    Raises:
        ValueError: If YAML syntax is invalid or schema is wrong

    Example:
        >>> mapping = load_cluster_tier_mapping(Path("config/cluster_labels_v1.yaml"))
        >>> mapping[3]  # Returns 1 (Tier 1)
        >>> mapping[0]  # Returns 2 (Tier 2)
    """
    # Handle missing file gracefully (NFR2.3 fault tolerance)
    if not config_path.exists():
        print(f"WARNING: Config file not found: {config_path}")
        print(f"Defaulting all clusters to Tier {default_tier} (safe fallback)")
        return {i: default_tier for i in range(num_clusters)}

    # Load YAML file
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML syntax in {config_path}: {e}")

    # Validate schema - must have cluster_tiers key
    if config is None or 'cluster_tiers' not in config:
        raise ValueError(
            f"Invalid config schema: missing 'cluster_tiers' key in {config_path}. "
            f"Expected format:\n"
            f"  cluster_tiers:\n"
            f"    0: 2\n"
            f"    1: 1\n"
            f"    ..."
        )

    mapping = dict(config['cluster_tiers'])

    # Fill missing clusters with default tier
    missing_clusters = []
    for cluster_id in range(num_clusters):
        if cluster_id not in mapping:
            mapping[cluster_id] = default_tier
            missing_clusters.append(cluster_id)

    if missing_clusters:
        print(f"WARNING: Clusters {missing_clusters} not in config, defaulting to Tier {default_tier}")

    # Log configuration
    version = config.get('version', 'unknown')
    print(f"Loaded cluster config version: {version}")

    tier1_clusters = sorted([c for c, t in mapping.items() if t == 1])
    tier2_clusters = sorted([c for c, t in mapping.items() if t == 2])

    print(f"  Tier 1 clusters ({len(tier1_clusters)}): {tier1_clusters}")
    print(f"  Tier 2 clusters ({len(tier2_clusters)}): {tier2_clusters}")

    return mapping


def classify_tiers_with_mapping(
    df: pd.DataFrame,
    cluster_tier_mapping: Dict[int, int]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Classify pairs into Tier 1 (auto-merge) and Tier 2 (review) using YAML mapping (Story 1.2).

    Args:
        df: Full DataFrame with cluster assignments
        cluster_tier_mapping: Dictionary mapping cluster ID -> tier (1 or 2)

    Returns:
        Tuple of (tier1_df, tier2_df)

    Example:
        >>> mapping = {0: 2, 1: 2, 3: 1, 4: 1}
        >>> tier1, tier2 = classify_tiers_with_mapping(df, mapping)
    """
    # Identify clusters for each tier
    tier1_clusters = {
        cluster_id
        for cluster_id, tier in cluster_tier_mapping.items()
        if tier == 1
    }

    # Split DataFrame by tier
    tier1_df = df[df['cluster'].isin(tier1_clusters)].copy()
    tier2_df = df[~df['cluster'].isin(tier1_clusters)].copy()

    return tier1_df, tier2_df


def calculate_tier_stats(
    tier1_df: pd.DataFrame,
    tier2_df: pd.DataFrame,
    validation_date: str = None,
    model_version: str = None
) -> Dict:
    """
    Calculate tier assignment statistics (Story 1.4).

    Args:
        tier1_df: Tier 1 (auto-merge) DataFrame
        tier2_df: Tier 2 (review queue) DataFrame
        validation_date: Date of LLM validation (optional)
        model_version: Model version string (optional)

    Returns:
        Dictionary with tier statistics
    """
    tier1_count = len(tier1_df)
    tier2_count = len(tier2_df)
    total = tier1_count + tier2_count

    return {
        'tier1_count': tier1_count,
        'tier2_count': tier2_count,
        'total_pairs': total,
        'tier1_pct': round((tier1_count / total) * 100, 1) if total > 0 else 0.0,
        'tier2_pct': round((tier2_count / total) * 100, 1) if total > 0 else 0.0,
        'validation_date': validation_date or 'unknown',
        'model_version': model_version or 'unknown',
    }


def calculate_cluster_stats(
    clustered_df: pd.DataFrame,
    fp_rates: Dict[int, float],
    cluster_tier_mapping: Dict[int, int]
) -> Dict[int, Dict]:
    """
    Calculate per-cluster statistics (Story 1.4).

    Args:
        clustered_df: DataFrame with cluster assignments
        fp_rates: Dictionary of cluster ID -> FP rate
        cluster_tier_mapping: Dictionary of cluster ID -> tier (1 or 2)

    Returns:
        Dictionary mapping cluster_id -> {count, fp_rate, tier}
    """
    cluster_counts = clustered_df['cluster'].value_counts().to_dict()

    stats = {}
    for cluster_id in sorted(set(cluster_counts.keys()) | set(fp_rates.keys())):
        stats[cluster_id] = {
            'count': cluster_counts.get(cluster_id, 0),
            'fp_rate': fp_rates.get(cluster_id, 0.0),
            'tier': cluster_tier_mapping.get(cluster_id, 2),
        }

    return stats


def generate_tier_report(
    tier_stats: Dict,
    cluster_stats: Dict[int, Dict],
    silhouette_score: float = None
) -> str:
    """
    Generate Markdown tier assignment validation report (Story 1.4).

    Args:
        tier_stats: Dictionary from calculate_tier_stats()
        cluster_stats: Dictionary from calculate_cluster_stats()
        silhouette_score: Optional silhouette score from clustering

    Returns:
        Markdown report string
    """
    lines = []

    # Header
    lines.append("# Tier Assignment Validation Report")
    lines.append("")
    lines.append(f"Generated: {tier_stats.get('validation_date', 'unknown')}")
    lines.append(f"Model Version: {tier_stats.get('model_version', 'unknown')}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Pairs | {tier_stats['total_pairs']:,} |")
    lines.append(f"| Tier 1 (Auto-Merge) | {tier_stats['tier1_count']:,} ({tier_stats['tier1_pct']:.1f}%) |")
    lines.append(f"| Tier 2 (Review Queue) | {tier_stats['tier2_count']:,} ({tier_stats['tier2_pct']:.1f}%) |")

    # Calculate manual review reduction
    # Assuming baseline is 100% manual review
    reduction = tier_stats['tier1_pct']
    lines.append(f"| Manual Review Reduction | {reduction:.1f}% |")
    lines.append("")

    # Cluster Distribution
    lines.append("## Cluster Distribution")
    lines.append("")

    # Tier 1 clusters
    tier1_clusters = {k: v for k, v in cluster_stats.items() if v['tier'] == 1}
    if tier1_clusters:
        lines.append("### Tier 1 Clusters (0% FP - Auto-Merge)")
        lines.append("")
        lines.append("| Cluster | Pairs | FP Rate | Status |")
        lines.append("|---------|-------|---------|--------|")
        for cluster_id in sorted(tier1_clusters.keys()):
            stats = tier1_clusters[cluster_id]
            lines.append(f"| {cluster_id} | {stats['count']:,} | {stats['fp_rate']:.1f}% | Auto-Merge |")
        lines.append("")

    # Tier 2 clusters
    tier2_clusters = {k: v for k, v in cluster_stats.items() if v['tier'] == 2}
    if tier2_clusters:
        lines.append("### Tier 2 Clusters (>0% FP - Manual Review)")
        lines.append("")
        lines.append("| Cluster | Pairs | FP Rate | Status |")
        lines.append("|---------|-------|---------|--------|")
        for cluster_id in sorted(tier2_clusters.keys()):
            stats = tier2_clusters[cluster_id]
            lines.append(f"| {cluster_id} | {stats['count']:,} | {stats['fp_rate']:.1f}% | Review |")
        lines.append("")

    # Validation Notes
    lines.append("## Validation Notes")
    lines.append("")
    if silhouette_score is not None:
        lines.append(f"- Silhouette Score: {silhouette_score:.3f}")
    else:
        lines.append("- Silhouette Score: N/A")
    lines.append("- Validation Method: LLM stratified sampling")
    lines.append("- Tier 1 Guarantee: 0% false positive rate")
    lines.append("")

    return "\n".join(lines)


def save_tier_report(report_content: str, report_path: Path) -> None:
    """
    Save tier report to file (Story 1.4).

    Args:
        report_content: Markdown report content
        report_path: Path to save report
    """
    report_path.write_text(report_content, encoding='utf-8')
    print(f"[OK] Saved tier report to: {report_path}")


def find_latest_run_directory(base_path: Path) -> Path:
    """
    Find the most recent run directory in the analysis folder.

    Args:
        base_path: Base path to analysis directory (e.g., _bmad-output/analysis)

    Returns:
        Path to the most recent run_* directory

    Raises:
        FileNotFoundError: If no run directories found
    """
    if not base_path.exists():
        raise FileNotFoundError(f"Analysis directory not found: {base_path}")

    run_dirs = sorted(base_path.glob("run_*"), reverse=True)
    if not run_dirs:
        raise FileNotFoundError(f"No run directories found in {base_path}")

    return run_dirs[0]


def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0  # psutil not installed


# ============================================================================
# Story 3.1: Programmatic Tier Assignment Function
# ============================================================================

# Configure module logger
logger = logging.getLogger(__name__)


def run_tier_assignment(
    input_dir: Path,
    config_path: Optional[Path] = None,
    stacked: bool = True
) -> Dict:
    """
    Run tier assignment programmatically (Story 3.1).

    This function allows Stage 3 (tier assignment) to be called from other
    scripts without using the command-line interface.

    Args:
        input_dir: Directory containing clustered_results.csv and llm_labeled_results.csv
        config_path: Optional path to YAML config with cluster-to-tier mappings
        stacked: If True (default), output stacked format (2 rows per pair).
                 If False, output wide format (1 row per pair with _i/_j suffixes).

    Returns:
        Dictionary with results:
        - success: bool - True if tier assignment completed successfully
        - tier1_count: int - Number of pairs in Tier 1 (auto-merge)
        - tier2_count: int - Number of pairs in Tier 2 (review queue)
        - elapsed_time: float - Execution time in seconds
        - error: str - Error message if success is False

    Example:
        >>> result = run_tier_assignment(Path("_bmad-output/analysis/run_20260110"))
        >>> if result['success']:
        ...     print(f"Tier 1: {result['tier1_count']} pairs")
    """
    start_time = time.time()
    input_dir = Path(input_dir)

    logger.info(f"Stage 3 (Tier Assignment) starting: {input_dir}")

    # File paths
    clustered_path = input_dir / 'clustered_results.csv'
    llm_labeled_path = input_dir / 'llm_labeled_results.csv'
    tier1_output = input_dir / 'auto_merge_pairs.csv'
    tier2_output = input_dir / 'review_queue_pairs.csv'

    # Load data
    try:
        clustered_df, fp_rates = load_clustered_results(clustered_path, llm_labeled_path)
    except (FileNotFoundError, ValueError) as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Stage 3 failed: {e}")
        return {
            'success': False,
            'tier1_count': 0,
            'tier2_count': 0,
            'elapsed_time': elapsed_time,
            'error': str(e)
        }

    # Classify tiers - use YAML config if provided, otherwise use FP rates
    logger.info("Classifying pairs into tiers...")
    if config_path is not None:
        try:
            cluster_tier_mapping = load_cluster_tier_mapping(config_path)
            tier1_df, tier2_df = classify_tiers_with_mapping(clustered_df, cluster_tier_mapping)
        except ValueError as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Stage 3 failed: {e}")
            return {
                'success': False,
                'tier1_count': 0,
                'tier2_count': 0,
                'elapsed_time': elapsed_time,
                'error': str(e)
            }
    else:
        tier1_df, tier2_df = classify_tiers(clustered_df, fp_rates, tier1_threshold=0.0)

    # Validate data integrity
    try:
        validate_tier_integrity(clustered_df, tier1_df, tier2_df)
    except AssertionError as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Stage 3 data integrity validation failed: {e}")
        return {
            'success': False,
            'tier1_count': 0,
            'tier2_count': 0,
            'elapsed_time': elapsed_time,
            'error': str(e)
        }

    # Add match_id column for unique pair identification
    tier1_df['match_id'] = tier1_df['i'].astype(str) + '_' + tier1_df['j'].astype(str)
    tier2_df['match_id'] = tier2_df['i'].astype(str) + '_' + tier2_df['j'].astype(str)

    # Rename score to confidence for clarity
    tier1_df = tier1_df.rename(columns={'score': 'confidence'})
    tier2_df = tier2_df.rename(columns={'score': 'confidence'})

    # Reorder columns per AC4: match_id, cluster, confidence, i, j, ...
    tier1_df = reorder_columns_for_ac4(tier1_df)
    tier2_df = reorder_columns_for_ac4(tier2_df)

    # Save tiered outputs (stacked or wide format)
    tier1_count = len(tier1_df)
    tier2_count = len(tier2_df)

    if stacked:
        tier1_stacked = wide_to_stacked(tier1_df)
        tier2_stacked = wide_to_stacked(tier2_df)
        tier1_output = input_dir / 'auto_merge_stacked.csv'
        tier2_output = input_dir / 'review_queue_stacked.csv'
        save_with_bom(tier1_stacked, tier1_output)
        save_with_bom(tier2_stacked, tier2_output)
    else:
        save_with_bom(tier1_df, tier1_output)
        save_with_bom(tier2_df, tier2_output)

    elapsed_time = time.time() - start_time
    total_count = tier1_count + tier2_count

    logger.info(
        f"Stage 3 (Tier Assignment) complete: "
        f"Tier 1={tier1_count:,} ({tier1_count/total_count*100:.1f}%), "
        f"Tier 2={tier2_count:,} ({tier2_count/total_count*100:.1f}%), "
        f"time={elapsed_time:.2f}s"
    )

    return {
        'success': True,
        'tier1_count': tier1_count,
        'tier2_count': tier2_count,
        'total_count': total_count,
        'elapsed_time': elapsed_time,
        'output_dir': str(input_dir),
        'tier1_path': str(tier1_output),
        'tier2_path': str(tier2_output),
    }


def main() -> int:
    """
    Main entry point for tier assignment script.

    Parses command-line arguments, loads data, classifies pairs into tiers,
    validates data integrity, and saves output files.

    Returns:
        Exit code: 0 for success, 1 for error
    """
    start_time = time.time()
    start_memory = get_memory_usage_mb()

    parser = argparse.ArgumentParser(
        description="Generate tiered outputs from clustered deduplication results"
    )
    parser.add_argument(
        '--input-dir',
        type=Path,
        default=None,
        help='Input directory containing clustered_results.csv and llm_labeled_results.csv. '
             'If not specified, auto-discovers the latest run directory.'
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=None,
        help='Path to YAML config file with cluster-to-tier mappings (Story 1.2). '
             'If not specified, uses FP-rate based classification from LLM labels.'
    )
    parser.add_argument(
        '--stacked',
        action='store_true',
        default=True,
        help='Output in stacked format (2 rows per pair with A/B positions). Default: True'
    )
    parser.add_argument(
        '--wide',
        action='store_true',
        default=False,
        help='Output in wide format (1 row per pair with _i/_j suffixes). Overrides --stacked.'
    )
    args = parser.parse_args()

    # --wide overrides --stacked
    use_stacked = not args.wide

    # Auto-discover input directory if not specified
    if args.input_dir is None:
        try:
            input_dir = find_latest_run_directory(Path('_bmad-output/analysis'))
            print(f"Auto-discovered latest run directory: {input_dir}")
        except FileNotFoundError as e:
            print(f"ERROR: {e}")
            print("Please specify --input-dir explicitly.")
            return 1
    else:
        input_dir = args.input_dir

    print("=" * 80)
    print("TIER ASSIGNMENT: Generate Auto-Merge and Review Queues")
    print("=" * 80)
    print()

    # File paths
    clustered_path = input_dir / 'clustered_results.csv'
    llm_labeled_path = input_dir / 'llm_labeled_results.csv'
    tier1_output = input_dir / 'auto_merge_pairs.csv'
    tier2_output = input_dir / 'review_queue_pairs.csv'

    # Load data
    try:
        clustered_df, fp_rates = load_clustered_results(clustered_path, llm_labeled_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}")
        return 1

    # Classify tiers - use YAML config if provided, otherwise use FP rates
    print("\nClassifying pairs into tiers...")
    if args.config is not None:
        # Story 1.2: YAML-based classification
        print(f"Using YAML configuration: {args.config}")
        try:
            cluster_tier_mapping = load_cluster_tier_mapping(args.config)
            tier1_df, tier2_df = classify_tiers_with_mapping(clustered_df, cluster_tier_mapping)
        except ValueError as e:
            print(f"ERROR: {e}")
            return 1
    else:
        # Story 1.1: FP-rate based classification
        print("Using FP-rate based classification (no config file specified)")
        tier1_df, tier2_df = classify_tiers(clustered_df, fp_rates, tier1_threshold=0.0)

    # Validate data integrity
    print("\nValidating data integrity...")
    try:
        validate_tier_integrity(clustered_df, tier1_df, tier2_df)
        print("[OK] Data integrity validated: No data loss, no duplicates")
    except AssertionError as e:
        print(f"ERROR: {e}")
        return 1

    # Add match_id column for unique pair identification
    tier1_df['match_id'] = tier1_df['i'].astype(str) + '_' + tier1_df['j'].astype(str)
    tier2_df['match_id'] = tier2_df['i'].astype(str) + '_' + tier2_df['j'].astype(str)

    # Rename score to confidence for clarity
    tier1_df = tier1_df.rename(columns={'score': 'confidence'})
    tier2_df = tier2_df.rename(columns={'score': 'confidence'})

    # Reorder columns per AC4: match_id, cluster, confidence, i, j, ...
    tier1_df = reorder_columns_for_ac4(tier1_df)
    tier2_df = reorder_columns_for_ac4(tier2_df)

    # Convert to stacked format if requested (default)
    if use_stacked:
        print("\nConverting to stacked format (2 rows per pair)...")
        tier1_stacked = wide_to_stacked(tier1_df)
        tier2_stacked = wide_to_stacked(tier2_df)
        tier1_output = input_dir / 'auto_merge_stacked.csv'
        tier2_output = input_dir / 'review_queue_stacked.csv'
        save_with_bom(tier1_stacked, tier1_output)
        save_with_bom(tier2_stacked, tier2_output)
        print(f"  Tier 1: {len(tier1_df):,} pairs -> {len(tier1_stacked):,} rows")
        print(f"  Tier 2: {len(tier2_df):,} pairs -> {len(tier2_stacked):,} rows")
    else:
        # Save in wide format (1 row per pair)
        print("\nSaving tiered outputs (wide format)...")
        save_with_bom(tier1_df, tier1_output)
        save_with_bom(tier2_df, tier2_output)

    # Performance metrics
    elapsed_time = time.time() - start_time
    end_memory = get_memory_usage_mb()
    peak_memory = max(end_memory, start_memory)

    # Summary
    print("\n" + "=" * 80)
    print("TIER ASSIGNMENT COMPLETE")
    print("=" * 80)
    print(f"\n[OK] Tier 1 (Auto-Merge): {len(tier1_df):,} pairs ({len(tier1_df) / len(clustered_df) * 100:.1f}%)")
    print(f"[OK] Tier 2 (Review Queue): {len(tier2_df):,} pairs ({len(tier2_df) / len(clustered_df) * 100:.1f}%)")
    print(f"[OK] Total: {len(clustered_df):,} pairs")
    print(f"\nPerformance Metrics:")
    print(f"  Execution time: {elapsed_time:.2f} seconds")
    if peak_memory > 0:
        print(f"  Memory usage: {peak_memory:.1f} MB")
    print(f"\nOutput files:")
    print(f"  - {tier1_output}")
    print(f"  - {tier2_output}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
