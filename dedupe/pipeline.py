from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import itertools
import os
import threading
from typing import Iterable
import numpy as np
import pandas as pd

from .config import DbConfig
from .io import create_mssql_engine, read_sql_df
from .preprocess import preprocess
from .blocking import (
    BlockingParams,
    compute_primary_key,
    compute_swap_invariant_key,
    compute_swap_fallback_for_secondary_split,
    compute_address_building_key,
    compute_address_typo_key,
    iter_blocks,
)
from .candidates import iter_exact_pairs, iter_fuzzy_pairs, iter_windowed_fuzzy_pairs
from .scoring import score_pair, MatchResult


def process_block(
    idx: np.ndarray,
    cols: dict[str, object],
    params: BlockingParams,
    fuzzy_threshold: float = 0.80,
    enable_address_aware: bool = True,
    use_windowed: bool = True,
    window_size: int = 10,
    *,
    global_seen: set[tuple[int, int]],
    global_lock: threading.Lock,
) -> list[MatchResult]:
    """
    Process a single block with global deduplication across passes.
    
    Args:
        idx: Block indices
        cols: Preprocessed columns
        params: Blocking parameters
        fuzzy_threshold: Minimum name similarity threshold
        enable_address_aware: Enable address-assisted matching
        use_windowed: Use windowed fuzzy pairs instead of process.extract
        window_size: Window size for sorted neighborhood
        global_seen: Set of already seen pairs across all blocks
        global_lock: Thread lock for global_seen access
    """
    results: list[MatchResult] = []
    local_seen: set[tuple[int, int]] = set()

    # Stage 1: Exact pairs (cheap, catches identical normalized names)
    for i, j in iter_exact_pairs(idx, cols):
        pair = (min(i, j), max(i, j))
        if pair in local_seen:
            continue
        local_seen.add(pair)

        with global_lock:
            if pair in global_seen:
                continue
            global_seen.add(pair)

        mr = score_pair(i, j, cols, fuzzy_threshold=fuzzy_threshold, enable_address_aware=enable_address_aware)
        if mr:
            results.append(mr)

    # Stage 2: Fuzzy pairs (name similarity with prefilter)
    if use_windowed:
        # Use sorted neighborhood windowing for address blocks
        for i, j in iter_windowed_fuzzy_pairs(idx, cols, window=window_size, name_threshold=88):
            pair = (min(i, j), max(i, j))
            if pair in local_seen:
                continue
            local_seen.add(pair)

            with global_lock:
                if pair in global_seen:
                    continue
                global_seen.add(pair)

            mr = score_pair(i, j, cols, fuzzy_threshold=fuzzy_threshold, enable_address_aware=enable_address_aware)
            if mr:
                results.append(mr)
    else:
        # Legacy: use process.extract for name-based blocks
        for i, j in iter_fuzzy_pairs(idx, cols, k=10, name_threshold=88):
            pair = (min(i, j), max(i, j))
            if pair in local_seen:
                continue
            local_seen.add(pair)

            with global_lock:
                if pair in global_seen:
                    continue
                global_seen.add(pair)

            mr = score_pair(i, j, cols, fuzzy_threshold=fuzzy_threshold, enable_address_aware=enable_address_aware)
            if mr:
                results.append(mr)

    return results


def _write_results(rows: Iterable[MatchResult], writer: csv.writer, df: pd.DataFrame) -> None:
    """
    Write results in the same format as duplicate_checker_optimized.py
    Creates 2 rows per match (one for record A, one for record B)
    """
    for mr in rows:
        record_a = df.iloc[mr.i]
        record_b = df.iloc[mr.j]
        
        # Create match_id from Crefo or indices
        crefo_a = str(record_a.get('Crefo', '')).strip()
        crefo_b = str(record_b.get('Crefo', '')).strip()
        match_id = f"{crefo_a}_{crefo_b}" if crefo_a and crefo_b else f"{mr.i}_{mr.j}"
        
        # Base row template
        base_row = {
            'match_id': match_id,
            'confidence': mr.score,
            'match_type': mr.reason
        }
        
        # Record A
        row_a = [
            base_row['match_id'],
            base_row['confidence'],
            base_row['match_type'],
            'A',  # position
            mr.i,  # index
            record_a.get('Vorname', ''),
            record_a.get('Name', ''),
            record_a.get('Name2', ''),
            record_a.get('Strasse', ''),
            record_a.get('HausNummer', ''),
            record_a.get('Plz', ''),
            record_a.get('Ort', ''),
            crefo_a,
            record_a.get('Geburtstag', ''),
            record_a.get('Jahrgang', ''),
        ]
        
        # Record B
        row_b = [
            base_row['match_id'],
            base_row['confidence'],
            base_row['match_type'],
            'B',  # position
            mr.j,  # index
            record_b.get('Vorname', ''),
            record_b.get('Name', ''),
            record_b.get('Name2', ''),
            record_b.get('Strasse', ''),
            record_b.get('HausNummer', ''),
            record_b.get('Plz', ''),
            record_b.get('Ort', ''),
            crefo_b,
            record_b.get('Geburtstag', ''),
            record_b.get('Jahrgang', ''),
        ]
        
        writer.writerow(row_a)
        writer.writerow(row_b)


def run_pipeline(
    query: str, 
    db_cfg: DbConfig, 
    out_path: str, 
    workers: int = 0, 
    chunksize: int = 200_000,
    fuzzy_threshold: float = 0.80, 
    enable_address_aware: bool = True,
    use_address_blocking: bool = True,
    window_size: int = 10
) -> None:
    """
    Run the deduplication pipeline with configurable blocking strategy.
    
    Args:
        query: SQL query to fetch data
        db_cfg: Database configuration
        out_path: Output CSV path
        workers: Number of worker threads (0 = auto)
        chunksize: SQL chunk size
        fuzzy_threshold: Name similarity threshold
        enable_address_aware: Enable address-assisted matching
        use_address_blocking: Use address-based blocking (True) or name-based (False)
        window_size: Window size for sorted neighborhood
    """
    engine = create_mssql_engine(db_cfg)
    dfs = read_sql_df(engine, query, chunksize=chunksize)
    if isinstance(dfs, pd.DataFrame):
        dfs = [dfs]

    max_workers = workers if workers > 0 else max(1, os.cpu_count() or 1)
    in_flight = max_workers * 2

    # TODO: Implement chunk boundary carry-over for address blocking
    # For now, process each chunk independently (may miss some duplicates at boundaries)
    carry_df = None

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Write header matching duplicate_checker_optimized.py format
        writer.writerow([
            "match_id", "confidence", "match_type", "position", "index",
            "vorname", "name", "name2", "strasse", "hausnummer", "plz", "ort",
            "crefo", "geburtstag", "jahrgang"
        ])

        for df_chunk in dfs:
            cols = preprocess(df_chunk)
            params = BlockingParams()

            if use_address_blocking:
                # Address-based blocking strategy
                # Pass A: Strict building-level blocking (PLZ + street_key + house_num)
                key_a = compute_address_building_key(cols)
                blocks_a = iter_blocks(key_a, params=params, cols=cols)

                # Pass B: Typo recovery (PLZ + house_num + street_sig)
                key_b = compute_address_typo_key(cols)
                blocks_b = iter_blocks(key_b, params=params, cols=cols)

                # Union both passes
                blocks = itertools.chain(blocks_a, blocks_b)
                use_windowed = True
            else:
                # Legacy name-based blocking strategy
                # Pass A: order-dependent blocking
                key_a = compute_primary_key(cols)
                blocks_a = iter_blocks(key_a, params=params, cols=cols)

                # Pass B: swap-invariant blocking
                key_b = compute_swap_invariant_key(cols)
                # Use swap-invariant fallback for secondary split in Pass B
                cols_b_split = dict(cols)
                cols_b_split["last"] = compute_swap_fallback_for_secondary_split(cols)
                blocks_b = iter_blocks(key_b, params=params, cols=cols_b_split)

                # Union both passes
                blocks = itertools.chain(blocks_a, blocks_b)
                use_windowed = False

            # Global deduplication across both passes
            global_seen: set[tuple[int, int]] = set()
            global_lock = threading.Lock()

            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = []
                for idx in blocks:
                    futures.append(
                        ex.submit(
                            process_block,
                            idx,
                            cols,
                            params,
                            fuzzy_threshold,
                            enable_address_aware,
                            use_windowed,
                            window_size,
                            global_seen=global_seen,
                            global_lock=global_lock,
                        )
                    )
                    if len(futures) >= in_flight:
                        for fut in as_completed(futures[:max_workers]):
                            _write_results(fut.result(), writer, df_chunk)
                            futures.remove(fut)

                for fut in as_completed(futures):
                    _write_results(fut.result(), writer, df_chunk)
