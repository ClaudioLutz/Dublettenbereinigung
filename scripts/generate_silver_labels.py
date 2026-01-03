"""
Generate silver labels from existing rule-based deduplication results.

This script extracts training data using weak supervision:
- Positives: High-confidence matches (≥95%, exact matches)
- Negatives: Hard negatives from same blocks or low-confidence pairs

Usage:
    python scripts/generate_silver_labels.py \\
        --results modular_results.csv \\
        --output data/silver_labels/labels_v1.csv \\
        --positive-threshold 95.0 \\
        --negative-ratio 2.5
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dedupe.ml_training.silver_labels import SilverLabelGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Generate silver labels for ML training")

    parser.add_argument(
        '--results',
        type=str,
        required=True,
        help='Path to rule-based deduplication results CSV',
    )
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='Path to output silver labels CSV',
    )
    parser.add_argument(
        '--positive-threshold',
        type=float,
        default=95.0,
        help='Minimum confidence for positive labels (default: 95.0)',
    )
    parser.add_argument(
        '--negative-ratio',
        type=float,
        default=2.5,
        help='Ratio of negatives to positives (default: 2.5)',
    )
    parser.add_argument(
        '--strategy',
        type=str,
        default='mixed',
        choices=['blocking', 'low_confidence', 'mixed'],
        help='Hard negative generation strategy (default: mixed)',
    )

    args = parser.parse_args()

    # Create generator
    generator = SilverLabelGenerator(
        positive_confidence_threshold=args.positive_threshold,
        negative_ratio=args.negative_ratio,
        hard_negative_strategy=args.strategy,
    )

    # Generate silver labels
    positives, negatives, combined = generator.generate_silver_labels(
        results_path=args.results,
        output_path=args.output,
    )

    logger.info("Silver label generation complete!")


if __name__ == '__main__':
    main()
