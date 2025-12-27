# scripts/run_splink_end2end.py
from __future__ import annotations
import sys
import argparse
from pathlib import Path

from dedupe.config import DbConfig
from dedupe_splink.stage import StageConfig, stage_query_to_parquet
from dedupe_splink.train import train_model_on_parquet_sample
from dedupe_splink.predict import predict_shard
from dedupe_splink.cluster import cluster_edges_to_mapping

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query-file", required=False, help="SQL query file (optional if using data.py)")
    ap.add_argument("--cache-dir", default="cache_splink", help="Parquet staging output")
    ap.add_argument("--out-dir", default="output_splink", help="Edges + clusters output")
    ap.add_argument("--unique-id-col", default="unique_id")
    ap.add_argument("--chunksize", type=int, default=200_000)

    ap.add_argument("--train-sample-glob", default=None,
                    help="Override sample glob for training (otherwise uses first shards)")
    ap.add_argument("--threshold", type=float, default=0.95)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--memory-limit", default="6GB")
    ap.add_argument("--use-data-py", action="store_true", 
                    help="Use query and DB config from data.py instead of query-file and env vars")

    args = ap.parse_args()

    # Get query and database config
    if args.use_data_py or args.query_file is None:
        # Import from data.py
        try:
            import data
            query = data.query
            # Create DbConfig from data.py settings (Windows Auth, no user/password)
            db_cfg = DbConfig(
                server=data.server,
                database=data.db,
                user="",  # Windows Auth
                password="",  # Windows Auth
                driver=data.driver,
                trust_server_certificate=True,
                encrypt=False  # Windows Auth typically doesn't need encryption
            )
            print(f"Using query and DB config from data.py")
            print(f"Server: {db_cfg.server}, Database: {db_cfg.database}")
        except ImportError as e:
            print(f"Error: Could not import data.py: {e}")
            sys.exit(1)
        except AttributeError as e:
            print(f"Error: data.py is missing required attributes (server, db, driver, query): {e}")
            sys.exit(1)
    else:
        # Use query file and environment variables
        query = Path(args.query_file).read_text(encoding="utf-8")
        db_cfg = DbConfig.from_env(prefix="DEDUPE_DB_")

    cache_dir = Path(args.cache_dir)
    out_dir = Path(args.out_dir)
    
    print(f"Cache directory: {cache_dir}")
    print(f"Output directory: {out_dir}")
    trained_json = out_dir / "model" / "trained_settings.json"

    # 1) Stage
    stage_cfg = StageConfig(out_dir=cache_dir, chunksize=args.chunksize, unique_id_col=args.unique_id_col)
    stage_query_to_parquet(query=query, db_cfg=db_cfg, cfg=stage_cfg)

    # 2) Train on a sample (no labels)
    if args.train_sample_glob:
        sample_glob = args.train_sample_glob
    else:
        # default: train on a subset of shards to keep training fast
        sample_glob = str(cache_dir / "shard=0*" / "*.parquet")

    train_model_on_parquet_sample(
        parquet_glob=sample_glob,
        out_settings_json=trained_json,
        unique_id_col=args.unique_id_col,
        threads=args.threads,
        memory_limit=args.memory_limit,
    )

    # 3) Predict per shard
    edges_dir = out_dir / "edges"
    for shard_path in sorted(cache_dir.glob("shard=*")):
        if not shard_path.is_dir():
            continue
        shard_name = shard_path.name.split("=", 1)[1]
        out_edges = edges_dir / f"shard={shard_name}.parquet"

        predict_shard(
            shard_dir=shard_path,
            trained_settings_json=trained_json,
            out_edges_parquet=out_edges,
            threshold_match_probability=args.threshold,
            threads=args.threads,
            memory_limit=args.memory_limit,
        )

    # 4) Cluster
    cluster_edges_to_mapping(
        edges_parquet_glob=str(edges_dir / "shard=*.parquet"),
        out_mapping_csv=out_dir / "clusters" / "cluster_mapping.csv",
    )

if __name__ == "__main__":
    main()
