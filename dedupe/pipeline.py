from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import itertools
import os
import threading
from typing import Iterable
import numpy as np
import pandas as pd
from tqdm import tqdm

from .config import DbConfig
from .io import create_mssql_engine, read_sql_df
from .preprocess import preprocess
from .swisstopo import SwisstopoAddressNormalizer
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
    ml_scorer=None,
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

        # Use ML scorer if provided, otherwise use rule-based
        if ml_scorer:
            mr = ml_scorer.score_pair(i, j, cols, fuzzy_threshold=fuzzy_threshold)
        else:
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

            # Use ML scorer if provided, otherwise use rule-based
            if ml_scorer:
                mr = ml_scorer.score_pair(i, j, cols, fuzzy_threshold=fuzzy_threshold)
            else:
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

            # Use ML scorer if provided, otherwise use rule-based
            if ml_scorer:
                mr = ml_scorer.score_pair(i, j, cols, fuzzy_threshold=fuzzy_threshold)
            else:
                mr = score_pair(i, j, cols, fuzzy_threshold=fuzzy_threshold, enable_address_aware=enable_address_aware)
            if mr:
                results.append(mr)

    return results


def _write_results(rows: Iterable[MatchResult], writer: csv.writer, df: pd.DataFrame, cols: dict[str, object]) -> None:
    """
    Write results in the same format as duplicate_checker_optimized.py
    Creates 2 rows per match (one for record A, one for record B)
    """
    # Helper to get value from cols (which might be Series or numpy array)
    def get_col(key, idx):
        if key not in cols:
            return ""
        val = cols[key]
        if isinstance(val, pd.Series):
            return val.iloc[idx]
        if isinstance(val, np.ndarray):
            return val[idx]
        return val

    # Fields to append from normalization
    norm_keys = [
        'street', 'house', 'plz4_used', 'ort',
        'addr_key_building', 'addr_key_typo',
        'swis_match_type', 'swis_changed',
        'swis_adr_egaid_ref', 'swis_bdg_egid_ref',
        'swis_street_label_ref', 'swis_adr_number_ref', 'swis_plz4_ref', 'swis_ort_ref'
    ]

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
        ] + [get_col(k, mr.i) for k in norm_keys]
        
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
        ] + [get_col(k, mr.j) for k in norm_keys]
        
        writer.writerow(row_a)
        writer.writerow(row_b)


def _write_audit_log(path: str, df: pd.DataFrame, cols: dict[str, object]) -> None:
    """
    Write separate audit log for rows where swis_changed is True.
    """
    # Check if we should append header (file doesn't exist)
    file_exists = os.path.exists(path)

    # Identify rows to log: only changed addresses
    if "swis_changed" not in cols:
        return

    # Values in cols are typically Series or ndarrays aligned with df
    changed = cols["swis_changed"]

    mask = (changed == True)
    if not mask.any():
        return

    # Helper to safely get from cols
    def get_series(key):
        val = cols.get(key)
        if isinstance(val, (pd.Series, np.ndarray)):
            # If it's a series, align it with the mask
            return val[mask]
        # Scalar fallback
        return pd.Series([val] * mask.sum())

    # Build audit dataframe
    # We use df.get() with fallback to handle missing columns gracefully
    len_df = len(df)
    empty_col = pd.Series([''] * len_df)

    audit_df = pd.DataFrame({
        'index': df.index[mask] if hasattr(df, 'index') else np.arange(len_df)[mask],
        'Crefo': df.get('Crefo', empty_col)[mask],
        'Strasse_raw': df.get('Strasse', empty_col)[mask],
        'HausNummer_raw': df.get('HausNummer', empty_col)[mask],
        'Plz_raw': df.get('Plz', empty_col)[mask],
        'Ort_raw': df.get('Ort', empty_col)[mask],

        'street_norm': get_series('street'),
        'house_norm': get_series('house'),
        'plz4_used': get_series('plz4_used'),
        'ort_norm': get_series('ort'),

        'swis_match_type': get_series('swis_match_type'),
        'swis_changed': get_series('swis_changed'),
        'swis_adr_egaid': get_series('swis_adr_egaid_ref'),
        'swis_bdg_egid': get_series('swis_bdg_egid_ref'),
        'swis_street_ref': get_series('swis_street_label_ref'),
        'swis_house_ref': get_series('swis_adr_number_ref'),
        'swis_plz4_ref': get_series('swis_plz4_ref'),
        'swis_ort_ref': get_series('swis_ort_ref'),
    })

    # Write to CSV
    audit_df.to_csv(path, mode='a', header=not file_exists, index=False)


def run_pipeline(
    query: str,
    db_cfg: DbConfig,
    out_path: str,
    workers: int = 0,
    chunksize: int = 200_000,
    fuzzy_threshold: float = 0.80,
    enable_address_aware: bool = True,
    use_address_blocking: bool = True,
    window_size: int = 10,
    swisstopo_db: str | None = None,
    norm_audit_out: str | None = None,
    ml_scorer=None,
    embedding_store=None,
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
        swisstopo_db: Optional path to swisstopo DuckDB file for address normalization
        norm_audit_out: Optional path to write normalization audit CSV
        ml_scorer: Optional ML scorer for ML-based matching
        embedding_store: Optional embedding store (used by ML scorer)
    """
    engine = create_mssql_engine(db_cfg)
    
    # Initialize swisstopo address normalizer if provided
    address_normalizer = None
    if swisstopo_db:
        from pathlib import Path
        if Path(swisstopo_db).exists():
            print(f"Loading swisstopo address index from {swisstopo_db}...")
            address_normalizer = SwisstopoAddressNormalizer(swisstopo_db)
            stats = address_normalizer.get_stats()
            print(f"  Loaded {stats['total_records']:,} addresses from {stats['unique_plz']:,} postal codes")
            print()
        else:
            print(f"Warning: Swisstopo database not found at {swisstopo_db}, skipping address normalization")
            print()

    # Remove existing audit log if it exists and we're starting fresh
    if norm_audit_out and os.path.exists(norm_audit_out):
        os.remove(norm_audit_out)
    
    # First pass: count total rows to estimate chunks
    print("Counting total rows...")
    # Remove ORDER BY clause for counting (SQL Server doesn't allow it in subqueries)
    import re
    query_no_order = re.sub(r'\s+ORDER\s+BY\s+.*?(?=\s*$)', '', query, flags=re.IGNORECASE | re.DOTALL)
    count_query = f"SELECT COUNT(*) as total FROM ({query_no_order}) as subq"
    try:
        total_rows = pd.read_sql(count_query, engine).iloc[0]['total']
        estimated_chunks = (total_rows + chunksize - 1) // chunksize
        print(f"Total rows: {total_rows:,} → Estimated chunks: {estimated_chunks}")
        print()
    except Exception as e:
        print(f"Could not count rows (non-critical): {e}")
        total_rows = None
        estimated_chunks = None
    
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
        header = [
            "match_id", "confidence", "match_type", "position", "index",
            "vorname", "name", "name2", "strasse", "hausnummer", "plz", "ort",
            "crefo", "geburtstag", "jahrgang"
        ]
        # Append normalization fields
        header += [
            "street_norm", "house_norm", "plz4_used", "ort_norm",
            "addr_key_building", "addr_key_typo",
            "swis_match_type", "swis_changed",
            "swis_adr_egaid", "swis_bdg_egid",
            "swis_street_ref", "swis_house_ref", "swis_plz4_ref", "swis_ort_ref"
        ]
        writer.writerow(header)

        chunk_num = 0
        for df_chunk in dfs:
            chunk_num += 1
            cols = preprocess(df_chunk, address_normalizer=address_normalizer)

            # Print normalization stats
            if "swis_match_type" in cols:
                match_types = cols["swis_match_type"]
                n_strict = (match_types == "strict").sum()
                n_sig = (match_types == "sig").sum()
                n_matched = n_strict + n_sig
                n_changed = cols["swis_changed"].sum()

                print(f"Chunk {chunk_num}: Normalization matched {n_matched} ({n_strict} strict, {n_sig} sig), {n_changed} keys changed")

            # Write audit log if requested
            if norm_audit_out:
                _write_audit_log(norm_audit_out, df_chunk, cols)

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

            # Convert generator to list to know total tasks for progress bar
            # This triggers the blocking computation (sort/split) which is fast
            blocks_list = list(blocks)
            total_blocks = len(blocks_list)
            
            # Build progress bar description with chunk info
            if estimated_chunks:
                chunk_info = f"Chunk {chunk_num}/{estimated_chunks}"
            else:
                chunk_info = f"Chunk {chunk_num}"
            pbar_desc = f"{chunk_info} - Processing blocks"

            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = []
                with tqdm(total=total_blocks, desc=pbar_desc, unit="block") as pbar:
                    for idx in blocks_list:
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
                                ml_scorer=ml_scorer,
                            )
                        )
                        if len(futures) >= in_flight:
                            # Wait for some futures to complete to keep memory usage in check
                            # Only wait for a subset (e.g., half of in_flight) to free up slots
                            subset = futures[:max_workers]
                            for fut in as_completed(subset):
                                _write_results(fut.result(), writer, df_chunk, cols)
                                futures.remove(fut)
                                pbar.update(1)

                    # Drain remaining futures
                    for fut in as_completed(futures):
                        _write_results(fut.result(), writer, df_chunk, cols)
                        pbar.update(1)
