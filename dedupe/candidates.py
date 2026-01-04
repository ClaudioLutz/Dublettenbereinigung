from __future__ import annotations

import itertools
from typing import Iterator, Tuple
import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process


def iter_exact_pairs(
    idx: np.ndarray, cols: dict[str, object], *, max_group: int = 200
) -> Iterator[Tuple[int, int]]:
    """
    Generate exact match pairs using swap-invariant unordered signature.
    This implements Stage 1 of the two-stage architecture.
    
    Uses min/max of (first, last_full) to create order-independent hash,
    where last_full = last + name2. This catches:
    - Hans Müller vs Müller Hans
    - Hans Müller + Name2=Bensel vs Müller Bensel Hans
    """
    first = cols["first"].iloc[idx].reset_index(drop=True).astype("string")
    last = cols["last"].iloc[idx].reset_index(drop=True).astype("string")
    name2 = cols["name2"].iloc[idx].reset_index(drop=True).astype("string")
    year = pd.Series(cols["year"][idx])

    # Combine last + name2 for comparison
    last_full = (last + " " + name2).str.strip().astype("string")

    # Create unordered signature: min/max of (first, last_full)
    a = first.to_numpy(dtype=object)
    b = last_full.to_numpy(dtype=object)
    mn = np.minimum(a, b)
    mx = np.maximum(a, b)

    # Hash the unordered signature + year
    tmp = pd.DataFrame({"a": mn, "b": mx, "y": year})
    h = pd.util.hash_pandas_object(tmp, index=False).to_numpy(dtype=np.uint64, copy=False)

    # Sort by hash and group
    order = np.argsort(h, kind="mergesort")
    h_sorted = h[order]
    idx_sorted = idx[order]

    s = 0
    n = len(idx_sorted)
    while s < n:
        e = s + 1
        while e < n and h_sorted[e] == h_sorted[s]:
            e += 1
        g = e - s
        if g > 1 and g <= max_group:
            group_ids = idx_sorted[s:e]
            for a, b in itertools.combinations(group_ids, 2):
                yield (int(a), int(b))
        s = e


def iter_fuzzy_pairs(
    idx: np.ndarray, cols: dict[str, object], *, k: int = 10, name_threshold: int = 88
) -> Iterator[Tuple[int, int]]:
    names = cols["full_name"].iloc[idx].tolist()
    pos_to_row = idx

    if len(idx) <= 400:
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                if fuzz.WRatio(names[i], names[j]) >= name_threshold:
                    yield (int(pos_to_row[i]), int(pos_to_row[j]))
        return

    for i, q in enumerate(names):
        matches = process.extract(
            q, names, scorer=fuzz.WRatio, score_cutoff=name_threshold, limit=k
        )
        for _, _, j in matches:
            if j <= i:
                continue
            yield (int(pos_to_row[i]), int(pos_to_row[j]))


def iter_windowed_fuzzy_pairs(
    idx: np.ndarray, 
    cols: dict[str, object], 
    *, 
    window: int = 10, 
    name_threshold: int = 88,
    sort_keys: list[str] | None = None
) -> Iterator[Tuple[int, int]]:
    """
    Generate candidate pairs using sorted neighborhood method with sliding window.
    
    This method is efficient for large address blocks where we want to compare
    records with similar names without doing all-pairs comparison.
    
    Args:
        idx: Block indices
        cols: Preprocessed columns
        window: Window size for comparisons (default: 10)
        name_threshold: Minimum name similarity score (default: 88)
        sort_keys: List of sort key types to use for multi-pass windowing.
                   Options: 'last_first', 'first_last', 'last_only'
                   Default: ['last_first', 'first_last']
    
    Yields:
        Tuples of (i, j) where i < j
    """
    if len(idx) <= 400:
        # For small blocks, use all-pairs (already efficient)
        for i in range(len(idx)):
            for j in range(i + 1, len(idx)):
                yield (int(idx[i]), int(idx[j]))
        return
    
    # Default sort keys: multi-pass with last+first and first+last
    if sort_keys is None:
        sort_keys = ['last_first', 'first_last']
    
    # Track seen pairs to avoid duplicates across passes
    seen_pairs: set[tuple[int, int]] = set()
    
    for sort_key_type in sort_keys:
        # Build sort key based on type
        sort_key = _build_sort_key(idx, cols, sort_key_type)
        
        # Sort indices by sort key
        sort_order = np.argsort(sort_key, kind='mergesort')
        sorted_idx = idx[sort_order]
        
        # Sliding window comparison
        n = len(sorted_idx)
        for i in range(n):
            # Compare with next 'window' records
            for j in range(i + 1, min(i + 1 + window, n)):
                row_i = int(sorted_idx[i])
                row_j = int(sorted_idx[j])
                
                # Ensure i < j for consistent pair representation
                pair = (min(row_i, row_j), max(row_i, row_j))
                
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                
                # Apply name threshold prefilter
                name_i = cols["full_name"].iloc[row_i]
                name_j = cols["full_name"].iloc[row_j]
                
                if name_i and name_j:
                    score = fuzz.WRatio(name_i, name_j)
                    if score >= name_threshold:
                        yield pair


def _build_sort_key(idx: np.ndarray, cols: dict[str, object], sort_key_type: str) -> np.ndarray:
    """
    Build sort key for sorted neighborhood windowing.
    
    Args:
        idx: Block indices
        cols: Preprocessed columns
        sort_key_type: Type of sort key ('last_first', 'first_last', 'last_only')
    
    Returns:
        Array of sort keys (strings)
    """
    first = cols["first"].iloc[idx].reset_index(drop=True).astype("string")
    last = cols["last"].iloc[idx].reset_index(drop=True).astype("string")
    name2 = cols["name2"].iloc[idx].reset_index(drop=True).astype("string")
    
    # Combine last + name2 for full surname
    last_full = (last + " " + name2).str.strip().astype("string")
    
    if sort_key_type == 'last_first':
        # Sort by: last_full | first
        return (last_full + "|" + first).to_numpy(dtype=object)
    
    elif sort_key_type == 'first_last':
        # Sort by: first | last_full (swap-friendly)
        return (first + "|" + last_full).to_numpy(dtype=object)
    
    elif sort_key_type == 'last_only':
        # Sort by: last | first (without name2)
        return (last + "|" + first).to_numpy(dtype=object)
    
    else:
        # Default: last_first
        return (last_full + "|" + first).to_numpy(dtype=object)
