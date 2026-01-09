"""
Pattern Discovery Analysis Module - Main Orchestrator.

This module coordinates all phases of pattern discovery:
- Phase 1: Foundation (clustering setup)
- Phase 2: Calibration (LLM validation)
- Phase 3: Full Analysis (225 pairs)
- Phase 4: Rule Implementation (feedback loop)
"""

import os
import argparse
import logging
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

from dedupe.analysis.utils import (
    load_modular_results,
    extract_features_for_all_pairs,
    convert_features_to_binary_matrix,
    get_feature_names
)
from dedupe.analysis.format_converter import convert_results_with_gender_to_pairs
from dedupe.analysis.clustering import (
    perform_kmodes_clustering,
    validate_k_silhouette,
    plot_cluster_validation,
    get_cluster_profiles,
    evaluate_clustering_quality
)
from sklearn.metrics import silhouette_score


def run_phase_1(
    input_path: str,
    output_dir: str,
    n_clusters: int = 15,
    skip_validation: bool = False
) -> dict:
    """
    Phase 1: Foundation - Clustering infrastructure.

    Args:
        input_path: Path to modular_results.csv
        output_dir: Output directory for results
        n_clusters: Number of clusters (default: 15)
        skip_validation: Skip expensive k validation (default: False)

    Returns:
        Dictionary with Phase 1 results and paths
    """
    print("\n" + "="*80)
    print("PHASE 1: FOUNDATION (Clustering Infrastructure)")
    print("="*80 + "\n")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Load modular results (with auto-detection of format)
    print("Step 1: Loading results...")

    # Check if file needs format conversion
    try:
        df = load_modular_results(input_path)
    except ValueError as e:
        if "Missing required columns" in str(e):
            print("Detected results_with_gender.csv format - converting to pair format...")
            df_converted = convert_results_with_gender_to_pairs(input_path)

            # Save converted file for future use
            converted_path = input_path.replace('.csv', '_pairs.csv')
            df_converted.to_csv(converted_path, index=False)
            print(f"Saved converted pairs to: {converted_path}")

            df = df_converted
        else:
            raise

    # Step 2: Extract rule features
    print("\nStep 2: Extracting rule features...")
    df_with_features = extract_features_for_all_pairs(df)

    # Step 3: Convert to binary matrix
    print("\nStep 3: Converting features to binary matrix...")
    feature_names = get_feature_names()
    X = convert_features_to_binary_matrix(df_with_features, feature_names)

    # Step 4: Run k-modes clustering
    print(f"\nStep 4: Running k-modes clustering with k={n_clusters}...")
    labels, centroids, cost = perform_kmodes_clustering(X, n_clusters=n_clusters, random_state=42)

    # Calculate Silhouette score (conditionally - expensive for large datasets)
    if not skip_validation:
        print("\nCalculating Silhouette score (this may take a few minutes)...")
        sil_score = silhouette_score(X, labels, metric='hamming')
        quality = evaluate_clustering_quality(sil_score)
        print(f"Clustering Quality: Silhouette Score = {sil_score:.4f}")
        print(f"Assessment: {quality}")
    else:
        # Skip expensive Silhouette calculation for large datasets
        sil_score = None
        quality = "SKIPPED (use --no-skip-validation to calculate)"
        print(f"\nClustering Quality: SKIPPED (validation disabled)")
        print(f"Clustering Cost: {cost:.2f}")

    # Add cluster labels to DataFrame
    df_with_features['cluster'] = labels

    # Step 5: Run Silhouette validation (k=5 to k=30) - OPTIONAL
    validation_results = None
    plot_path = None

    if not skip_validation:
        print("\nStep 5: Running Silhouette validation (k=5 to k=30)...")
        print("NOTE: This is computationally expensive and may take 15-30 minutes.")
        validation_results = validate_k_silhouette(X, k_range=range(5, 31))

        # Step 6: Generate cluster validation plots
        print("\nStep 6: Generating cluster validation plots...")
        plot_path = os.path.join(output_dir, 'cluster_validation.png')
        plot_cluster_validation(
            validation_results['silhouette'],
            validation_results['cost'],
            current_k=n_clusters,
            output_path=plot_path
        )
    else:
        print("\nStep 5-6: SKIPPED (--skip-validation flag set)")

    # Step 7: Generate cluster profiles
    print("\nStep 7: Generating cluster profiles...")
    profiles_df = get_cluster_profiles(centroids, feature_names)

    # Step 8: Save results
    print("\nStep 8: Saving results...")

    # Save clustered results (all pairs with cluster assignments)
    clustered_results_path = os.path.join(output_dir, 'clustered_results.csv')
    df_with_features.to_csv(clustered_results_path, index=False)
    print(f"Saved clustered results: {clustered_results_path}")

    # Save cluster profiles
    profiles_path = os.path.join(output_dir, 'cluster_profiles.csv')
    profiles_df.to_csv(profiles_path, index=False)
    print(f"Saved cluster profiles: {profiles_path}")

    # Save validation results (if available)
    validation_path = None
    if validation_results is not None:
        validation_path = os.path.join(output_dir, 'silhouette_validation.csv')
        validation_df = pd.DataFrame({
            'k': list(validation_results['silhouette'].keys()),
            'silhouette_score': list(validation_results['silhouette'].values()),
            'cost': list(validation_results['cost'].values())
        })
        validation_df.to_csv(validation_path, index=False)
        print(f"Saved validation results: {validation_path}")

    # Print cluster sizes
    print("\nCluster Sizes:")
    cluster_sizes = np.bincount(labels)
    for cluster_id, size in enumerate(cluster_sizes):
        print(f"  Cluster {cluster_id}: {size} pairs ({size/len(labels)*100:.1f}%)")

    # Phase 1 summary
    print("\n" + "="*80)
    print("PHASE 1 COMPLETE")
    print("="*80)
    print(f"Total pairs processed: {len(df_with_features)}")
    print(f"Features extracted: {len(feature_names)}")
    print(f"Clusters created: {n_clusters}")
    if sil_score is not None:
        print(f"Silhouette score: {sil_score:.4f} ({quality})")
    else:
        print(f"Silhouette score: {quality}")
    print(f"Clustering cost: {cost:.2f}")
    print(f"Output directory: {output_dir}")
    print("="*80 + "\n")

    return {
        'clustered_results_path': clustered_results_path,
        'profiles_path': profiles_path,
        'validation_path': validation_path,
        'plot_path': plot_path,
        'silhouette_score': sil_score,
        'n_clusters': n_clusters,
        'n_pairs': len(df_with_features),
        'quality_assessment': quality
    }


def run_phase_2(
    clustered_results_path: str,
    output_dir: str,
    n_calibration_pairs: int = 30
) -> dict:
    """
    Phase 2: LLM Calibration - Validate confidence thresholds.

    Args:
        clustered_results_path: Path to clustered_results.csv from Phase 1
        output_dir: Output directory for results
        n_calibration_pairs: Number of pairs to manually label (default: 30)

    Returns:
        Dictionary with Phase 2 results
    """
    print("\n" + "="*80)
    print("PHASE 2: LLM CALIBRATION")
    print("="*80 + "\n")

    print("Phase 2 calibration workflow:")
    print("  1. Stratified sample 30 pairs across clusters")
    print("  2. Manual labeling by user (interactive)")
    print("  3. DeepSeek LLM labeling of same pairs")
    print("  4. Accuracy comparison by confidence tier")
    print("  5. Recommend confidence threshold")
    print("\nNote: This phase requires interactive user input and DeepSeek API key.")
    print("Phase 2 implementation is pending - requires interactive manual labeling workflow.")
    print("="*80 + "\n")

    return {
        'status': 'pending',
        'message': 'Phase 2 requires interactive implementation'
    }


def run_phase_3(
    clustered_results_path: str,
    output_dir: str,
    confidence_threshold: float = 0.85
) -> dict:
    """
    Phase 3: Full Analysis - Pattern discovery on 225 pairs.

    Args:
        clustered_results_path: Path to clustered_results.csv from Phase 1
        output_dir: Output directory for results
        confidence_threshold: LLM confidence threshold (default: 0.85)

    Returns:
        Dictionary with Phase 3 results
    """
    print("\n" + "="*80)
    print("PHASE 3: FULL ANALYSIS")
    print("="*80 + "\n")

    print("Phase 3 full analysis workflow:")
    print("  1. Stratified sample 225 pairs (15 per cluster)")
    print("  2. DeepSeek LLM labeling with confidence scoring")
    print("  3. Manual review of low-confidence pairs")
    print("  4. Pattern analysis (disagreement identification)")
    print("  5. Generate pattern report with recommendations")
    print("  6. Categorize pairs into ground truth files")
    print("\nNote: This phase requires DeepSeek API key and manual review.")
    print("Phase 3 implementation is pending - requires LLM integration and interactive review.")
    print("="*80 + "\n")

    return {
        'status': 'pending',
        'message': 'Phase 3 requires DeepSeek API and interactive review'
    }


def setup_logging(output_dir: str, log_level: str = 'INFO') -> None:
    """
    Configure logging for pattern discovery analysis.

    Args:
        output_dir: Directory to write log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Create output directory if needed
    os.makedirs(output_dir, exist_ok=True)

    # Log file path
    log_file = os.path.join(output_dir, 'pattern_discovery.log')

    # Log format
    log_format = '[%(asctime)s] %(levelname)s - %(name)s:%(lineno)d - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(),  # Console output
            logging.FileHandler(log_file, mode='a')  # File output
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized - log file: {log_file}")
    logger.info(f"Log level: {log_level}")


def main():
    """Main entry point for pattern discovery analysis."""
    parser = argparse.ArgumentParser(
        description='Pattern Discovery Analysis Module',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run Phase 1 only
  python -m dedupe.analysis.pattern_discovery --phase 1

  # Run all phases
  python -m dedupe.analysis.pattern_discovery --phase all

  # Custom cluster count
  python -m dedupe.analysis.pattern_discovery --phase 1 --clusters 20
        """
    )

    parser.add_argument(
        '--input',
        default='modular_results.csv',
        help='Path to modular_results.csv (default: modular_results.csv)'
    )

    parser.add_argument(
        '--output-dir',
        default='_bmad-output/analysis',
        help='Output directory (default: _bmad-output/analysis)'
    )

    parser.add_argument(
        '--phase',
        choices=['1', '2', '3', '4', 'all'],
        required=True,
        help='Which phase to run (1-4 or all)'
    )

    parser.add_argument(
        '--clusters',
        type=int,
        default=15,
        help='Number of clusters (default: 15)'
    )

    parser.add_argument(
        '--confidence-threshold',
        type=float,
        default=0.85,
        help='LLM confidence threshold (default: 0.85)'
    )

    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip expensive k-value validation (recommended for large datasets)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        return 1

    if args.clusters < 5 or args.clusters > 50:
        print(f"ERROR: clusters must be between 5 and 50, got {args.clusters}")
        return 1

    if not 0.0 <= args.confidence_threshold <= 1.0:
        print(f"ERROR: confidence-threshold must be between 0.0 and 1.0, got {args.confidence_threshold}")
        return 1

    # Create timestamped output directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = os.path.join(args.output_dir, f'run_{timestamp}')

    # Setup logging
    setup_logging(args.output_dir, log_level='INFO')
    logger = logging.getLogger(__name__)

    logger.info("="*80)
    logger.info("Pattern Discovery Analysis Module")
    logger.info(f"Input: {args.input}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Phase: {args.phase}")
    logger.info(f"Clusters: {args.clusters}")
    logger.info("="*80)

    # Execute requested phase
    if args.phase in ['1', 'all']:
        results_phase1 = run_phase_1(args.input, output_dir, args.clusters, args.skip_validation)

        # Check if clustering quality is acceptable (only if calculated)
        if results_phase1['silhouette_score'] is not None and results_phase1['silhouette_score'] < 0.3:
            print("\nWARNING: Clustering quality is POOR (Silhouette < 0.3)")
            print("Results may not be reliable. Consider:")
            print("  - Trying different k values (see silhouette_validation.csv)")
            print("  - Reviewing cluster_validation.png for optimal k")
            print("  - Checking if data has sufficient pattern diversity")
            return 1

    if args.phase in ['2', 'all']:
        print("\nPhase 2 not yet implemented (coming soon)")

    if args.phase in ['3', 'all']:
        print("\nPhase 3 not yet implemented (coming soon)")

    if args.phase in ['4', 'all']:
        print("\nPhase 4 not yet implemented (coming soon)")

    print("\nPattern discovery analysis complete!")
    return 0


if __name__ == '__main__':
    exit(main())
