from __future__ import annotations

import sys
import argparse
import getpass
from pathlib import Path

from dedupe.config import DbConfig
from dedupe.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run optimized dedupe pipeline")
    parser.add_argument("--query-file", required=True, help="Path to SQL query file")
    parser.add_argument("--out", required=True, help="Output CSV path")
    parser.add_argument("--workers", type=int, default=0, help="Number of worker threads (0=auto)")
    parser.add_argument("--prompt-password", action="store_true", help="Prompt for DB password instead of env var")
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

    run_pipeline(query=query, db_cfg=cfg, out_path=args.out, workers=args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
