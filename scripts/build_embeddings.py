"""
Build embeddings for all address records.

This script generates sentence embeddings for the entire address database:
1. Connects to SQL Server and reads address data in chunks
2. Preprocesses and normalizes fields
3. Generates embeddings using sentence-transformers
4. Saves to memory-mapped storage for efficient access
5. Builds FAISS index for fast similarity search

Usage:
    python scripts/build_embeddings.py \\
        --query-file query.sql \\
        --db-server SERVERNAME \\
        --db-database DBNAME \\
        --output-dir models/embeddings \\
        --batch-size 256 \\
        --device cuda

    For testing on a subset:
    python scripts/build_embeddings.py \\
        --query-file query.sql \\
        --db-server SERVERNAME \\
        --db-database DBNAME \\
        --output-dir models/embeddings_test \\
        --limit 10000 \\
        --device cpu
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dedupe.io import get_engine, read_sql_df
from dedupe.ml.config import BATCH_SIZE, CHUNK_SIZE, DEVICE, MODEL_VERSION, NAME_ONLY_VERSION_SUFFIX
from dedupe.ml.embeddings import EmbeddingGenerator, EmbeddingStore
from dedupe.preprocess import preprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate embeddings for address deduplication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Database connection
    parser.add_argument(
        '--query-file',
        type=str,
        required=True,
        help='Path to SQL query file defining input data',
    )
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

    # Output configuration
    parser.add_argument(
        '--output-dir',
        type=str,
        default='models/embeddings',
        help='Directory to save embeddings and index (default: models/embeddings)',
    )

    # Processing configuration
    parser.add_argument(
        '--batch-size',
        type=int,
        default=BATCH_SIZE,
        help=f'Batch size for embedding generation (default: {BATCH_SIZE})',
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=CHUNK_SIZE,
        help=f'Number of records to process per chunk (default: {CHUNK_SIZE})',
    )
    parser.add_argument(
        '--device',
        type=str,
        default=DEVICE,
        choices=['auto', 'cuda', 'cpu'],
        help=f'Device for embedding generation (default: {DEVICE})',
    )

    # Testing/debugging
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of records to process (for testing)',
    )
    parser.add_argument(
        '--skip-faiss',
        action='store_true',
        help='Skip FAISS index building (faster for testing)',
    )

    # Name-only embeddings (for improved entity matching)
    parser.add_argument(
        '--name-only',
        action='store_true',
        help='Generate name-only embeddings (recommended for entity matching). '
             'These embeddings exclude address fields to avoid address contamination.',
    )

    return parser.parse_args()


def main():
    """Main entry point for embedding generation."""
    args = parse_args()

    # Resolve database connection from args or environment
    db_server = args.db_server or os.getenv('DEDUPE_DB_SERVER')
    db_database = args.db_database or os.getenv('DEDUPE_DB_DATABASE')

    if not db_server or not db_database:
        logger.error(
            "Database connection not specified. "
            "Provide --db-server and --db-database, or set DEDUPE_DB_SERVER and DEDUPE_DB_DATABASE env vars."
        )
        sys.exit(1)

    # Read query file
    query_path = Path(args.query_file)
    if not query_path.exists():
        logger.error(f"Query file not found: {query_path}")
        sys.exit(1)

    with open(query_path, 'r', encoding='utf-8') as f:
        query = f.read()

    # Apply limit for testing
    if args.limit:
        # Add TOP clause to SQL query (SQL Server syntax)
        if 'SELECT' in query.upper():
            query = query.replace('SELECT', f'SELECT TOP {args.limit}', 1)
        logger.info(f"Limiting to {args.limit} records for testing")

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 80)
    logger.info("EMBEDDING GENERATION PIPELINE")
    logger.info("=" * 80)
    logger.info(f"Database: {db_server}/{db_database}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Device: {args.device}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Chunk size: {args.chunk_size}")
    logger.info(f"Name-only mode: {args.name_only}")
    logger.info("=" * 80)

    if args.name_only:
        logger.info("NOTE: Generating name-only embeddings (no address fields)")
        logger.info("      These are recommended for proper entity matching")

    start_time = time.time()

    # Initialize embedding generator
    logger.info("Initializing embedding generator...")
    generator = EmbeddingGenerator(
        device=args.device,
        batch_size=args.batch_size,
        show_progress=True,
    )

    # Connect to database
    logger.info("Connecting to database...")
    engine = get_engine(db_server, db_database)

    # Prepare storage
    all_texts = []
    all_metadata = {
        'crefo': [],
        'index': [],
    }

    # Process data in chunks
    logger.info("Reading and preprocessing data...")
    total_records = 0

    for chunk_idx, df_chunk in enumerate(read_sql_df(engine, query, chunksize=args.chunk_size)):
        logger.info(f"Processing chunk {chunk_idx + 1} ({len(df_chunk)} records)")

        # Preprocess chunk
        # Note: We don't use Swisstopo normalization here since we want raw text diversity
        cols = preprocess(df_chunk, address_normalizer=None)

        # Prepare texts for this chunk
        chunk_texts = []
        for i in range(len(df_chunk)):
            text = generator.prepare_text(
                first=cols['first'][i] if i < len(cols['first']) else '',
                last=cols['last'][i] if i < len(cols['last']) else '',
                name2=cols['name2'][i] if i < len(cols['name2']) else '',
                street=cols['street'][i] if i < len(cols['street']) else '',
                house=cols['house'][i] if i < len(cols['house']) else '',
                plz=cols['plz4_used'][i] if i < len(cols['plz4_used']) else '',
                ort=cols['ort'][i] if i < len(cols['ort']) else '',
                name_only=args.name_only,  # Use name-only mode if specified
            )
            chunk_texts.append(text)

        all_texts.extend(chunk_texts)

        # Store metadata
        all_metadata['crefo'].extend(df_chunk['Crefo'].values)
        all_metadata['index'].extend(df_chunk.index.values)

        total_records += len(df_chunk)

        logger.info(f"Total records processed: {total_records}")

        # For testing, break after limit reached
        if args.limit and total_records >= args.limit:
            break

    logger.info(f"Preprocessed {total_records} records")

    # Generate embeddings
    logger.info("Generating embeddings...")
    version_suffix = NAME_ONLY_VERSION_SUFFIX if args.name_only else ""
    embeddings_path = output_dir / f"embeddings_{MODEL_VERSION}{version_suffix}.dat"

    # Use memory-efficient encoding for large datasets
    embeddings_already_saved = False
    if total_records > 100_000:
        generator.encode_large_dataset(
            all_texts,
            embeddings_path,
            chunk_size=args.batch_size * 10,  # Process in larger chunks
        )
        embeddings_already_saved = True
        # Load back for EmbeddingStore
        embeddings = np.memmap(
            embeddings_path,
            dtype='float32',
            mode='r',
            shape=(total_records, 384),
        )
    else:
        # For smaller datasets, encode directly
        embeddings = generator.encode_batch(all_texts)
        logger.info(f"Generated embeddings shape: {embeddings.shape}")

    # Convert metadata to numpy arrays
    all_metadata['crefo'] = np.array(all_metadata['crefo'])
    all_metadata['index'] = np.array(all_metadata['index'])
    all_metadata['timestamp'] = np.array([datetime.now().isoformat()])
    all_metadata['model_name'] = np.array([generator.model_name])

    # Create EmbeddingStore
    logger.info("Creating embedding store...")
    store = EmbeddingStore(embeddings, all_metadata, faiss_index=None)

    # Build FAISS index
    if not args.skip_faiss:
        logger.info("Building FAISS index...")
        try:
            store.build_faiss_index()
        except ImportError:
            logger.warning("FAISS not installed. Skipping index building.")
    else:
        logger.info("Skipping FAISS index building (--skip-faiss)")

    # Save everything
    logger.info("Saving embedding store...")
    store.save(output_dir, skip_embeddings=embeddings_already_saved, version_suffix=version_suffix)

    # Calculate statistics
    elapsed_time = time.time() - start_time
    records_per_sec = total_records / elapsed_time if elapsed_time > 0 else 0

    logger.info("=" * 80)
    logger.info("EMBEDDING GENERATION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total records processed: {total_records:,}")
    logger.info(f"Embedding dimension: {embeddings.shape[1]}")
    logger.info(f"Total time: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
    logger.info(f"Throughput: {records_per_sec:.1f} records/second")
    logger.info(f"Output directory: {output_dir}")
    logger.info("=" * 80)

    # Print sample embeddings for validation
    logger.info("Sample embeddings:")
    for i in range(min(3, len(all_texts))):
        logger.info(f"  Record {i}:")
        logger.info(f"    Text: {all_texts[i][:100]}...")
        logger.info(f"    Embedding norm: {np.linalg.norm(embeddings[i]):.4f}")
        logger.info(f"    Crefo: {all_metadata['crefo'][i]}")

    # Test similarity between first two records
    if len(embeddings) >= 2:
        sim_0_1 = store.get_similarity(0, 1, metric='cosine')
        logger.info(f"Cosine similarity between records 0 and 1: {sim_0_1:.4f}")

    logger.info("Done!")


if __name__ == '__main__':
    main()
