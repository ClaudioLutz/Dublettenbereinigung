"""
Run the complete deduplication pipeline end-to-end.

This script orchestrates all stages of the pipeline:
- Stage 1: Deduplication (run_dedupe.py)
- Stage 2.1: Clustering (pattern_discovery.py)
- Stage 2.2: LLM Validation (phase2_llm_labeling.py)
- Stage 3: Tier Assignment (generate_tiered_output.py)

Usage:
    python scripts/run_full_pipeline.py --query-file query.sql
    python scripts/run_full_pipeline.py --query-file query.sql --llm-samples 500
    python scripts/run_full_pipeline.py --input existing_results.csv  # Skip Stage 1

Arguments:
    --query-file: SQL file for Stage 1 database query
    --input: Skip Stage 1, use existing CSV file
    --llm-samples: Number of LLM samples (default: 500)
    --clusters: Number of clusters for Stage 2.1 (default: 15)
    --wide: Output wide format instead of stacked (default: stacked)
"""

import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*80}")
    print(f"STAGE: {description}")
    print(f"{'='*80}")
    print(f"Command: {' '.join(cmd)}\n")

    start = time.time()
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    elapsed = time.time() - start

    if result.returncode == 0:
        print(f"\n[OK] {description} completed in {elapsed:.1f}s")
        return True
    else:
        print(f"\n[ERROR] {description} failed with exit code {result.returncode}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run complete deduplication pipeline end-to-end"
    )

    # Stage 1 options
    stage1_group = parser.add_mutually_exclusive_group(required=True)
    stage1_group.add_argument(
        '--query-file',
        type=Path,
        help='SQL file for Stage 1 database query'
    )
    stage1_group.add_argument(
        '--input',
        type=Path,
        help='Skip Stage 1, use existing CSV file as input'
    )

    # Stage 1 additional options
    parser.add_argument(
        '--blocking-mode',
        default='address',
        choices=['address', 'name', 'both'],
        help='Blocking mode for Stage 1 (default: address)'
    )
    parser.add_argument(
        '--fuzzy-threshold',
        type=float,
        default=0.80,
        help='Fuzzy matching threshold (default: 0.80)'
    )

    # Stage 2 options
    parser.add_argument(
        '--clusters',
        type=int,
        default=15,
        help='Number of clusters for Stage 2.1 (default: 15)'
    )
    parser.add_argument(
        '--llm-samples',
        type=int,
        default=500,
        help='Minimum LLM samples for Stage 2.2 (default: 500)'
    )

    # Stage 3 options
    parser.add_argument(
        '--wide',
        action='store_true',
        help='Output wide format instead of stacked (default: stacked)'
    )

    # General options
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help='Output directory (default: auto-generated timestamp)'
    )

    args = parser.parse_args()

    pipeline_start = time.time()
    print("\n" + "="*80)
    print("DEDUPLICATION PIPELINE - FULL RUN")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Determine output file for Stage 1
    if args.input:
        stage1_output = args.input
        print(f"\nSkipping Stage 1, using existing file: {stage1_output}")
    else:
        stage1_output = Path('modular_results_fresh.csv')

    # =========================================================================
    # Stage 1: Deduplication
    # =========================================================================
    if args.query_file:
        cmd = [
            sys.executable, 'scripts/run_dedupe.py',
            '--query-file', str(args.query_file),
            '--out', str(stage1_output),
            '--blocking-mode', args.blocking_mode,
            '--fuzzy-threshold', str(args.fuzzy_threshold),
            '--window-size', '10',
            '--workers', '0'
        ]
        if not run_command(cmd, "Stage 1: Deduplication"):
            return 1

    # =========================================================================
    # Stage 2.1: Clustering
    # =========================================================================
    # Convert to pairs format for clustering
    pairs_output = stage1_output.with_name(stage1_output.stem + '_pairs.csv')

    cmd = [
        sys.executable, '-m', 'dedupe.analysis.pattern_discovery',
        '--input', str(stage1_output),
        '--phase', '1',
        '--clusters', str(args.clusters),
        '--skip-validation'
    ]
    if not run_command(cmd, "Stage 2.1: Clustering"):
        return 1

    # Find the latest run directory
    analysis_dir = Path('_bmad-output/analysis')
    run_dirs = sorted(analysis_dir.glob('run_*'), reverse=True)
    if not run_dirs:
        print("[ERROR] No run directory found after clustering")
        return 1
    latest_run = run_dirs[0]
    print(f"\nUsing run directory: {latest_run}")

    # =========================================================================
    # Stage 2.2: LLM Validation
    # =========================================================================
    samples_per_cluster = max(1, args.llm_samples // args.clusters)

    cmd = [
        sys.executable, 'scripts/phase2_llm_labeling.py',
        '--run-dir', str(latest_run),
        '--samples-per-cluster', str(samples_per_cluster)
    ]
    if not run_command(cmd, "Stage 2.2: LLM Validation"):
        return 1

    # =========================================================================
    # Stage 3: Tier Assignment
    # =========================================================================
    cmd = [
        sys.executable, 'scripts/generate_tiered_output.py',
        '--input-dir', str(latest_run)
    ]
    if args.wide:
        cmd.append('--wide')

    if not run_command(cmd, "Stage 3: Tier Assignment"):
        return 1

    # =========================================================================
    # Summary
    # =========================================================================
    pipeline_elapsed = time.time() - pipeline_start

    print("\n" + "="*80)
    print("PIPELINE COMPLETE")
    print("="*80)
    print(f"Total time: {pipeline_elapsed:.1f}s ({pipeline_elapsed/60:.1f} minutes)")
    print(f"\nOutput directory: {latest_run}")
    print(f"\nFinal output files:")

    if args.wide:
        print(f"  - {latest_run / 'auto_merge_pairs.csv'}")
        print(f"  - {latest_run / 'review_queue_pairs.csv'}")
    else:
        print(f"  - {latest_run / 'auto_merge_stacked.csv'}")
        print(f"  - {latest_run / 'review_queue_stacked.csv'}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
