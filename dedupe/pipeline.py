from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import os
from typing import Iterable
import numpy as np
import pandas as pd

from .config import DbConfig
from .io import create_mssql_engine, read_sql_df
from .preprocess import preprocess
from .blocking import BlockingParams, compute_primary_key, iter_blocks
from .candidates import iter_exact_pairs, iter_fuzzy_pairs
from .scoring import score_pair, MatchResult


def process_block(idx: np.ndarray, cols: dict[str, object], params: BlockingParams) -> list[MatchResult]:
    results: list[MatchResult] = []

    for i, j in iter_exact_pairs(idx, cols):
        mr = score_pair(i, j, cols)
        if mr:
            results.append(mr)

    for i, j in iter_fuzzy_pairs(idx, cols, k=10, name_threshold=88):
        mr = score_pair(i, j, cols)
        if mr:
            results.append(mr)

    return results


def _write_results(rows: Iterable[MatchResult], writer: csv.writer) -> None:
    for mr in rows:
        writer.writerow([mr.i, mr.j, mr.score, mr.name_score, mr.addr_score, mr.reason])


def run_pipeline(query: str, db_cfg: DbConfig, out_path: str, workers: int = 0) -> None:
    engine = create_mssql_engine(db_cfg)
    df = read_sql_df(engine, query)
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Expected a DataFrame from read_sql_df")

    cols = preprocess(df)
    key = compute_primary_key(cols)
    params = BlockingParams()

    max_workers = workers if workers > 0 else max(1, os.cpu_count() or 1)
    in_flight = max_workers * 2

    blocks = iter_blocks(key, params=params, cols=cols)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["i", "j", "score", "name_score", "addr_score", "reason"])

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = []
            for idx in blocks:
                futures.append(ex.submit(process_block, idx, cols, params))
                if len(futures) >= in_flight:
                    for fut in as_completed(futures[:max_workers]):
                        _write_results(fut.result(), writer)
                        futures.remove(fut)

            for fut in as_completed(futures):
                _write_results(fut.result(), writer)
