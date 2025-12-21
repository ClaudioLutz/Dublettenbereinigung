import argparse
import os
import json
import logging
import pandas as pd
import duckdb
from splink import DuckDBAPI, Linker
from dedupe_splink.stage import extract_sql_to_parquet
from dedupe_splink.settings import get_settings
from dedupe_splink.clustering import cluster_edges
from data import create_db_engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Splink Deduplication Pipeline")
    parser.add_argument("--query-file", type=str, help="Path to SQL query file")
    parser.add_argument("--out", type=str, required=True, help="Output directory for results")
    parser.add_argument("--parquet-cache", type=str, required=True, help="Directory for Parquet shards")
    parser.add_argument("--trained-settings", type=str, default="trained_settings.json", help="Path to trained settings JSON")
    parser.add_argument("--db-user", type=str, help="DB User")
    parser.add_argument("--db-password", type=str, help="DB Password")
    parser.add_argument("--extract-only", action="store_true", help="Run only extraction")
    parser.add_argument("--train-only", action="store_true", help="Run only training")
    parser.add_argument("--inference-only", action="store_true", help="Run only inference (skip extraction/training)")

    args = parser.parse_args()

    db_api = DuckDBAPI()

    # 1. Extraction
    if not args.inference_only and not args.train_only:
        if args.query_file:
            logger.info("Starting extraction...")
            # Load query
            with open(args.query_file, 'r') as f:
                query = f.read()

            # Connect to DB
            engine = create_db_engine(args.db_user, args.db_password)
            if not engine:
                logger.error("Could not connect to database.")
                return

            extract_sql_to_parquet(engine, query, args.parquet_cache)
            logger.info("Extraction complete.")
        else:
            logger.info("No query file provided. Assuming Parquet cache exists.")

    if args.extract_only:
        return

    # 2. Training
    if not args.inference_only:
        logger.info("Starting training...")
        if os.path.exists(args.trained_settings) and not args.train_only:
             logger.info(f"Trained settings found at {args.trained_settings}. Skipping training (use --train-only to force).")
        else:
            # Load sample
            parquet_files = []
            for root, dirs, files in os.walk(args.parquet_cache):
                for f in files:
                    if f.endswith('.parquet'):
                        parquet_files.append(os.path.join(root, f))

            if not parquet_files:
                logger.error("No parquet files found for training.")
                return

            # Read a sample
            sample_df_list = []
            total_rows = 0
            for f in parquet_files[:5]:
                df = pd.read_parquet(f)
                sample_df_list.append(df)
                total_rows += len(df)
                if total_rows > 200000:
                    break

            if not sample_df_list:
                logger.error("Could not load sample.")
                return

            sample_df = pd.concat(sample_df_list)

            if 'unique_id' not in sample_df.columns:
                 sample_df['unique_id'] = range(len(sample_df))

            # Initialize Linker
            settings = get_settings()
            linker = Linker(sample_df, settings, db_api)

            # Estimate U
            logger.info("Estimating U probabilities...")
            linker.training.estimate_u_using_random_sampling(max_pairs=1e6)

            # Estimate M
            logger.info("Estimating M probabilities...")

            m_blocking_rule = "l.plz_prefix3 = r.plz_prefix3 AND l.surname_initial = r.surname_initial"

            linker.training.estimate_parameters_using_expectation_maximisation(
                blocking_rule=m_blocking_rule,
                estimate_without_term_frequencies=True
            )

            # Save settings
            # Fixed: use linker.misc.save_model_to_json
            linker.misc.save_model_to_json(args.trained_settings, overwrite=True)
            logger.info(f"Saved trained settings to {args.trained_settings}")

    if args.train_only:
        return

    # 3. Inference (Shard by Shard)
    logger.info("Starting inference...")

    shards = [d for d in os.listdir(args.parquet_cache) if d.startswith('shard=')]

    output_dir = args.out
    os.makedirs(output_dir, exist_ok=True)

    for shard in shards:
        logger.info(f"Processing {shard}...")
        shard_path = os.path.join(args.parquet_cache, shard)

        files_pattern = os.path.join(shard_path, "*.parquet")

        db_path = os.path.join(shard_path, "db.duckdb")
        con = duckdb.connect(db_path)

        con.execute(f"CREATE OR REPLACE TABLE input_data AS SELECT * FROM read_parquet('{files_pattern}')")

        cols = [c[0] for c in con.execute("DESCRIBE input_data").fetchall()]
        if 'unique_id' not in cols:
             # Add a unique_id column using row_number (unstable if re-run, but allows execution)
             con.execute("CREATE OR REPLACE TABLE input_data AS SELECT *, row_number() OVER () as unique_id FROM input_data")

        # Linker
        # Use DuckDBAPI with connection
        shard_db_api = DuckDBAPI(connection=con)
        linker = Linker("input_data", args.trained_settings, shard_db_api)

        # Predict
        logger.info(f"Predicting for {shard}...")
        predictions = linker.inference.predict(threshold_match_probability=0.95)

        pred_df = predictions.as_pandas_dataframe()

        if not pred_df.empty:
            logger.info(f"Clustering {len(pred_df)} edges...")
            clusters = cluster_edges(pred_df)

            shard_out_dir = os.path.join(output_dir, shard)
            os.makedirs(shard_out_dir, exist_ok=True)

            pred_df.to_parquet(os.path.join(shard_out_dir, "pairs.parquet"), index=False)
            clusters.to_parquet(os.path.join(shard_out_dir, "clusters.parquet"), index=False)
        else:
            logger.info("No matches found in shard.")

        con.close()

    logger.info("Inference complete.")

if __name__ == "__main__":
    main()
