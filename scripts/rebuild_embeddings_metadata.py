"""
Rebuild embeddings metadata file.

This script regenerates the embeddings_v1_meta.npz file that may have been
lost or corrupted. It requires database access to get Crefo values.

Usage:
    python scripts/rebuild_embeddings_metadata.py --embeddings-dir models/embeddings
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dedupe.io import get_engine, read_sql_df
from dedupe.ml.config import EMBEDDING_DIM, EMBEDDING_DTYPE, MODEL_VERSION

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Rebuild embeddings metadata file")
    parser.add_argument(
        '--embeddings-dir',
        type=str,
        default='models/embeddings',
        help='Directory containing embeddings (default: models/embeddings)',
    )
    parser.add_argument(
        '--query-file',
        type=str,
        default='query.sql',
        help='Path to SQL query file (default: query.sql)',
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
    return parser.parse_args()


def main():
    args = parse_args()

    # Resolve database connection
    db_server = args.db_server or os.getenv('DEDUPE_DB_SERVER')
    db_database = args.db_database or os.getenv('DEDUPE_DB_DATABASE')

    if not db_server or not db_database:
        logger.error("Database connection not specified.")
        sys.exit(1)

    # Check embeddings file exists
    embeddings_dir = Path(args.embeddings_dir)
    embeddings_path = embeddings_dir / f"embeddings_{MODEL_VERSION}.dat"

    if not embeddings_path.exists():
        logger.error(f"Embeddings file not found: {embeddings_path}")
        sys.exit(1)

    # Calculate number of records from file size
    file_size = embeddings_path.stat().st_size
    n_records = file_size // (EMBEDDING_DIM * 4)  # float32 = 4 bytes
    logger.info(f"Embeddings file size: {file_size:,} bytes")
    logger.info(f"Calculated number of records: {n_records:,}")

    # Read query
    query_path = Path(args.query_file)
    if not query_path.exists():
        logger.error(f"Query file not found: {query_path}")
        sys.exit(1)

    with open(query_path, 'r', encoding='utf-8') as f:
        query = f.read()

    # Connect to database
    logger.info(f"Connecting to {db_server}/{db_database}...")
    engine = get_engine(db_server, db_database)

    # Read only Crefo values (faster query)
    logger.info("Reading Crefo values from database...")
    all_crefos = []
    all_indices = []
    total = 0

    for chunk_idx, df_chunk in enumerate(read_sql_df(engine, query, chunksize=100000)):
        all_crefos.extend(df_chunk['Crefo'].values)
        all_indices.extend(range(total, total + len(df_chunk)))
        total += len(df_chunk)
        logger.info(f"Read {total:,} records...")

        if total >= n_records:
            # Trim to exact count
            all_crefos = all_crefos[:n_records]
            all_indices = all_indices[:n_records]
            break

    logger.info(f"Total records: {len(all_crefos):,}")

    # Create metadata
    metadata = {
        'crefo': np.array(all_crefos),
        'index': np.array(all_indices),
        'timestamp': np.array([datetime.now().isoformat()]),
        'model_name': np.array(['paraphrase-multilingual-MiniLM-L12-v2']),
    }

    # Save metadata
    metadata_path = embeddings_dir / f"embeddings_{MODEL_VERSION}_meta.npz"
    np.savez(metadata_path, **metadata)
    logger.info(f"Metadata saved to {metadata_path}")

    # Verify
    loaded = np.load(metadata_path, allow_pickle=True)
    logger.info(f"Verification - loaded {len(loaded['index'])} indices")
    logger.info("Done!")


if __name__ == '__main__':
    main()
