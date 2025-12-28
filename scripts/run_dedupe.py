from __future__ import annotations

import sys
import argparse
import getpass
from pathlib import Path

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
    
    print(f"Running deduplication pipeline:")
    print(f"  Blocking mode: {args.blocking_mode}")
    print(f"  Fuzzy threshold: {args.fuzzy_threshold}")
    print(f"  Window size: {args.window_size}")
    print(f"  Address-aware matching: {enable_address_aware}")
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
        window_size=args.window_size
    )
    
    print(f"\nDeduplication complete. Results written to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
