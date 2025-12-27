# scripts/run_splink_predict.py
from __future__ import annotations
import sys
import argparse
from pathlib import Path

from dedupe_splink.predict import predict_shard

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", required=True, help="Parquet staging output")
    ap.add_argument("--out-dir", required=True, help="Edges output dir")
    ap.add_argument("--threshold", type=float, default=0.95)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--memory-limit", default="6GB")

    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    out_dir = Path(args.out_dir)
    trained_json = out_dir / "model" / "trained_settings.json"
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

if __name__ == "__main__":
    main()
