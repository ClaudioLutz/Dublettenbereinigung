# scripts/run_splink_end2end.py
from __future__ import annotations
import argparse
from pathlib import Path

from dedupe.config import DbConfig
from dedupe_splink.stage import StageConfig, stage_query_to_parquet
from dedupe_splink.train import train_model_on_parquet_sample
from dedupe_splink.predict import predict_shard
from dedupe_splink.cluster import cluster_edges_to_mapping

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query-file", required=True)
    ap.add_argument("--cache-dir", required=True, help="Parquet staging output")
    ap.add_argument("--out-dir", required=True, help="Edges + clusters output")
    ap.add_argument("--unique-id-col", default="unique_id")
    ap.add_argument("--chunksize", type=int, default=200_000)

    ap.add_argument("--train-sample-glob", default=None,
                    help="Override sample glob for training (otherwise uses first shards)")
    ap.add_argument("--threshold", type=float, default=0.95)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--memory-limit", default="6GB")

    args = ap.parse_args()

    query = Path(args.query_file).read_text(encoding="utf-8")
    db_cfg = DbConfig.from_env(prefix="DEDUPE_DB_")

    cache_dir = Path(args.cache_dir)
    out_dir = Path(args.out_dir)
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
