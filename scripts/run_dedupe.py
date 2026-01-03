from __future__ import annotations

import sys
import argparse
import getpass
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path to import local dedupe module
sys.path.insert(0, str(Path(__file__).parent.parent))

from dedupe.config import DbConfig
from dedupe.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run optimized dedupe pipeline")
    parser.add_argument("--query-file", required=True, help="Path to SQL query file")
    parser.add_argument("--out", required=True, help="Output CSV path")
    parser.add_argument("--workers", type=int, default=0, help="Number of worker threads (0=auto)")
    parser.add_argument("--prompt-password", action="store_true", help="Prompt for DB password instead of env var")
    
    # Blocking strategy options
    parser.add_argument(
        "--blocking-mode",
        choices=["address", "name"],
        default="address",
        help="Blocking strategy: 'address' (new, address-based) or 'name' (legacy, name-based). Default: address"
    )
    parser.add_argument("--fuzzy-threshold", type=float, default=0.80, help="Fuzzy name similarity threshold (default: 0.80)")
    parser.add_argument("--window-size", type=int, default=10, help="Window size for sorted neighborhood (default: 10)")
    parser.add_argument("--no-address-aware", action="store_true", help="Disable address-assisted matching")
    
    # Address normalization options
    parser.add_argument(
        "--swisstopo-db",
        type=str,
        default=None,
        help="Path to swisstopo DuckDB file for reference-based address normalization (optional)"
    )
    parser.add_argument(
        "--norm-audit-out",
        type=str,
        default=None,
        help="Path to write normalization audit CSV (for matched/changed addresses)"
    )

    # ML scoring options (Phase 4)
    parser.add_argument(
        "--use-ml-scoring",
        action="store_true",
        help="Use ML-based scoring instead of rule-based fuzzy matching"
    )
    parser.add_argument(
        "--ml-model-dir",
        type=str,
        default="models",
        help="Directory containing ML model artifacts (default: models)"
    )
    parser.add_argument(
        "--ml-version",
        type=str,
        default="v1",
        help="ML model version to load (default: v1)"
    )
    parser.add_argument(
        "--embeddings-dir",
        type=str,
        default=None,
        help="Directory containing pre-computed embeddings (optional, improves ML quality)"
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    query_path = Path(args.query_file)
    query = query_path.read_text(encoding="utf-8")

    cfg = DbConfig.from_env()
    if args.prompt_password:
        pw = getpass.getpass("DB password: ")
        cfg = DbConfig(
            server=cfg.server,
            database=cfg.database,
            user=cfg.user,
            password=pw,
            driver=cfg.driver,
            trust_server_certificate=cfg.trust_server_certificate,
            encrypt=cfg.encrypt,
        )

    use_address_blocking = (args.blocking_mode == "address")
    enable_address_aware = not args.no_address_aware

    # Load ML scorer if requested
    ml_scorer = None
    embedding_store = None

    if args.use_ml_scoring:
        print("Loading ML scorer...")
        try:
            # Load embeddings if provided
            if args.embeddings_dir:
                from dedupe.ml.embeddings import EmbeddingStore
                embedding_store = EmbeddingStore.load(args.embeddings_dir)
                print(f"  Loaded embeddings from {args.embeddings_dir}")

            # Load ML scorer
            from dedupe.ml.scoring_ml import MLScorer
            ml_scorer = MLScorer.load_from_directory(
                model_dir=args.ml_model_dir,
                version=args.ml_version,
                embedding_store=embedding_store,
            )
            print(f"  Loaded ML model version {args.ml_version} from {args.ml_model_dir}")
        except Exception as e:
            print(f"  Warning: Failed to load ML scorer: {e}")
            print(f"  Falling back to rule-based scoring...")
            ml_scorer = None

    print(f"\nRunning deduplication pipeline:")
    print(f"  Scoring method: {'ML-based' if ml_scorer else 'Rule-based'}")
    print(f"  Blocking mode: {args.blocking_mode}")
    print(f"  Fuzzy threshold: {args.fuzzy_threshold}")
    print(f"  Window size: {args.window_size}")
    print(f"  Address-aware matching: {enable_address_aware}")
    print(f"  Swisstopo normalization: {'enabled' if args.swisstopo_db else 'disabled'}")
    print(f"  Workers: {args.workers if args.workers > 0 else 'auto'}")
    print(f"  Output: {args.out}")
    print()

    run_pipeline(
        query=query,
        db_cfg=cfg,
        out_path=args.out,
        workers=args.workers,
        fuzzy_threshold=args.fuzzy_threshold,
        enable_address_aware=enable_address_aware,
        use_address_blocking=use_address_blocking,
        window_size=args.window_size,
        swisstopo_db=args.swisstopo_db,
        norm_audit_out=args.norm_audit_out,
        ml_scorer=ml_scorer,
        embedding_store=embedding_store,
    )
    
    print(f"\nDeduplication complete. Results written to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
