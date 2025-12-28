# scripts/run_splink_train.py
from __future__ import annotations
import sys
import argparse
from pathlib import Path

# Add project root to path to import local dedupe_splink module
sys.path.insert(0, str(Path(__file__).parent.parent))

from dedupe_splink.train import train_model_on_parquet_sample

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", required=True, help="Parquet staging output")
    ap.add_argument("--out-dir", required=True, help="Model output dir")
    ap.add_argument("--unique-id-col", default="unique_id")
    ap.add_argument("--train-sample-glob", default=None)

    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    out_dir = Path(args.out_dir)
    trained_json = out_dir / "model" / "trained_settings.json"

    if args.train_sample_glob:
        sample_glob = args.train_sample_glob
    else:
        sample_glob = str(cache_dir / "shard=0*" / "*.parquet")

    train_model_on_parquet_sample(
        parquet_glob=sample_glob,
        out_settings_json=trained_json,
        unique_id_col=args.unique_id_col,
    )

if __name__ == "__main__":
    main()
