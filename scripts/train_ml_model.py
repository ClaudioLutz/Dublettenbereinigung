"""
Train ML model for entity matching.

This script runs the complete training pipeline:
1. Generate silver labels from rule-based results
2. Load data and extract features
3. Train LightGBM model with cross-validation
4. Calibrate model using isotonic regression
5. Save model and calibrator

Usage:
    python scripts/train_ml_model.py \\
        --results modular_results.csv \\
        --query query.sql \\
        --db-server SERVERNAME \\
        --db-database DBNAME \\
        --output-dir models \\
        --embeddings models/embeddings \\
        --use-cv
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from dedupe.ml.embeddings import EmbeddingStore
from dedupe.ml_training.train import TrainingPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Train ML model for entity matching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input files
    parser.add_argument(
        '--results',
        type=str,
        required=True,
        help='Path to rule-based deduplication results CSV',
    )
    parser.add_argument(
        '--query',
        type=str,
        required=True,
        help='Path to SQL query file',
    )

    # Database connection
    parser.add_argument(
        '--db-server',
        type=str,
        help='SQL Server hostname (or set DEDUPE_DB_SERVER env var)',
    )
    parser.add_argument(
        '--db-database',
        type=str,
        help='SQL Server database name (or set DEDUPE_DB_DATABASE env var)',
    )

    # Embeddings
    parser.add_argument(
        '--embeddings',
        type=str,
        default=None,
        help='Path to embeddings directory (optional, improves model quality)',
    )

    # Output
    parser.add_argument(
        '--output-dir',
        type=str,
        default='models',
        help='Output directory for trained models (default: models)',
    )
    parser.add_argument(
        '--version',
        type=str,
        default='v1',
        help='Model version identifier (default: v1)',
    )

    # Silver label parameters
    parser.add_argument(
        '--positive-threshold',
        type=float,
        default=95.0,
        help='Confidence threshold for positive labels (default: 95.0)',
    )
    parser.add_argument(
        '--negative-ratio',
        type=float,
        default=2.5,
        help='Ratio of negatives to positives (default: 2.5)',
    )

    # Training parameters
    parser.add_argument(
        '--use-cv',
        action='store_true',
        help='Use cross-validation during training (slower but more robust)',
    )
    parser.add_argument(
        '--random-state',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)',
    )

    args = parser.parse_args()

    # Resolve database connection
    db_server = args.db_server or os.getenv('DEDUPE_DB_SERVER')
    db_database = args.db_database or os.getenv('DEDUPE_DB_DATABASE')

    if not db_server or not db_database:
        logger.error(
            "Database connection not specified. "
            "Provide --db-server and --db-database, or set environment variables."
        )
        sys.exit(1)

    # Load embeddings if provided
    embedding_store = None
    name_embedding_store = None
    if args.embeddings:
        embeddings_path = Path(args.embeddings)
        if embeddings_path.exists():
            # Load full embeddings (name + address)
            logger.info(f"Loading full embeddings from {embeddings_path}")
            try:
                embedding_store = EmbeddingStore.load(embeddings_path)
                logger.info("Full embeddings loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load full embeddings: {e}")
                logger.warning("Continuing without full embeddings...")

            # Load name-only embeddings (critical for proper entity matching)
            logger.info(f"Loading name-only embeddings from {embeddings_path}")
            try:
                name_embedding_store = EmbeddingStore.load_name_only(embeddings_path)
                logger.info("Name-only embeddings loaded successfully")
            except FileNotFoundError:
                logger.warning("Name-only embeddings not found. Run with --name-only to generate them.")
                logger.warning("Continuing without name-only embeddings...")
            except Exception as e:
                logger.warning(f"Failed to load name-only embeddings: {e}")
                logger.warning("Continuing without name-only embeddings...")
        else:
            logger.warning(f"Embeddings directory not found: {embeddings_path}")
            logger.warning("Continuing without embeddings...")

    # Initialize training pipeline
    pipeline = TrainingPipeline(
        embedding_store=embedding_store,
        name_embedding_store=name_embedding_store,
        random_state=args.random_state,
    )

    # Run complete pipeline
    try:
        metrics = pipeline.run_complete_pipeline(
            results_path=args.results,
            query_path=args.query,
            db_server=db_server,
            db_database=db_database,
            output_dir=args.output_dir,
            positive_threshold=args.positive_threshold,
            negative_ratio=args.negative_ratio,
            use_cv=args.use_cv,
            version=args.version,
        )

        logger.info("Training completed successfully!")
        logger.info(f"Final test AUC: {metrics.get('test_auc', 0):.4f}")

    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
